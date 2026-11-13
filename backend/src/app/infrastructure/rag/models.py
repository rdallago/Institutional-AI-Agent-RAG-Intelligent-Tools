"""Coordinacion entre proceso HTTP e ingesta local; nunca espera cupo."""
import os
from pathlib import Path

from app.application.ia.exceptions import IAOcupada
from app.infrastructure.llm.work_gate import MemoryModelWorkGate


class LocalModelGate:
    def __init__(self, path=None):
        self.memory=MemoryModelWorkGate()
        self.path=path or Path(__file__).resolve().parents[4]/'.model-work.lock'

    def try_acquire(self):
        lease=self.memory.try_acquire()
        stream=None
        try:
            stream=open(self.path,'a+b')
            if stream.tell()==0: stream.write(b'0');stream.flush()
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            if stream:stream.close()
            lease.release()
            raise IAOcupada(retry_after=1) from None
        class Held:
            released=False
            def release(self):
                if not self.released:
                    self.released=True
                    stream.close()
                    lease.release()
        return Held()


class CoordinatedDirectProvider:
    def __init__(self,provider,gate):
        self.provider,self.gate=provider,gate
        self.idle=None

    async def generate(self,input):
        config=getattr(self.provider,'_config',None)
        if config is not None and config.provider == 'ollama' and not config.testing and config.enforce_memory_guard:
            from app.infrastructure.rag.resources import require_memory
            require_memory(1.5)
        lease=self.gate.try_acquire()
        try:
            if self.idle is not None:await self.idle()
            return await self.provider.generate(input)
        finally:lease.release()
