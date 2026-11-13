# Artefactos oficiales PG18, fijados al manifest linux/amd64.
FROM pgvector/pgvector:0.8.2-pg18-trixie@sha256:77f3220c156665b2b198f3bcb859bdd6c12f6dd614e0a835f36826e21eaeb475 AS extension
# Misma base inmutable que los contenedores actuales: no bajar version menor.
FROM postgres:18@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4
COPY --from=extension /usr/lib/postgresql/18/lib/vector.so /usr/lib/postgresql/18/lib/vector.so
COPY --from=extension /usr/share/postgresql/18/extension/vector* /usr/share/postgresql/18/extension/
COPY --from=extension /usr/share/doc/pgvector /usr/share/doc/pgvector
LABEL org.opencontainers.image.title="api-usuarios-clean PostgreSQL 18 pgvector"
LABEL org.opencontainers.image.description="Candidato aislado; no activa vector ni migra bases al arrancar"
RUN postgres --version | grep -E '^postgres \(PostgreSQL\) 18\.' \
    && test -f /usr/share/postgresql/18/extension/vector.control \
    && grep -Fx "default_version = '0.8.2'" /usr/share/postgresql/18/extension/vector.control \
    && ldd /usr/lib/postgresql/18/lib/vector.so > /tmp/vector-ldd \
    && ! grep -q 'not found' /tmp/vector-ldd \
    && rm /tmp/vector-ldd
