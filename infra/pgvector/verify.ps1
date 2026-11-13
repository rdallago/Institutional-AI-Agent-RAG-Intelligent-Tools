# Solo ensayo aislado. No lee .env ni usa Compose, puertos o volumenes existentes.
$ErrorActionPreference = 'Stop'
$image = 'api-usuarios-clean/pgvector:18-0.8.2-93c'
$name = 'api-usuarios-93c-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$containerId = $null
function Assert-Docker {
    if ($LASTEXITCODE -ne 0) { throw 'Fallo Docker en ensayo aislado.' }
}
try {
    $containerId = docker run -d --name $name --label 'app.sprint=93c-isolated' --network none --cpus 0.5 --memory 256m --memory-swap 256m --shm-size 16m --tmpfs '/var/lib/postgresql:rw,size=192m' -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=rag93c_synthetic -e POSTGRES_USER=synthetic_admin $image postgres -c listen_addresses= -c shared_buffers=32MB -c work_mem=1MB -c maintenance_work_mem=16MB -c max_connections=10
    Assert-Docker
    if ($containerId -notmatch '^[0-9a-f]{64}$') { throw 'ID temporal invalido.' }
    $ready = $false
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        docker exec $containerId pg_isready -q -U synthetic_admin -d rag93c_synthetic
        if ($LASTEXITCODE -eq 0) { $ready=$true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Servidor sintetico no disponible.' }
    # Guardar inspeccion reducida: no hay volumenes ni puertos heredados.
    docker inspect $containerId --format '{{.Id}} {{.HostConfig.NetworkMode}} {{json .Mounts}} {{json .HostConfig.PortBindings}} {{json .HostConfig.Tmpfs}}'
    Assert-Docker
    Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'smoke.sql') | docker exec -i $containerId psql -X -v ON_ERROR_STOP=1 -U synthetic_admin -d rag93c_synthetic
    Assert-Docker
    docker exec $containerId pg_dump -U synthetic_admin -d rag93c_synthetic -Fc -f /tmp/synthetic.dump
    Assert-Docker
    docker exec $containerId sha256sum /tmp/synthetic.dump
    Assert-Docker
    docker exec $containerId pg_restore --list /tmp/synthetic.dump
    Assert-Docker
    docker exec $containerId createdb -U synthetic_admin rag93c_restored
    Assert-Docker
    docker exec $containerId pg_restore -U synthetic_admin -d rag93c_restored --exit-on-error /tmp/synthetic.dump
    Assert-Docker
    $restored = docker exec $containerId psql -X -At -v ON_ERROR_STOP=1 -U synthetic_admin -d rag93c_restored -c "SELECT count(*)::text || ':' || min(vector_dims(embedding))::text || ':' || (SELECT extversion FROM pg_extension WHERE extname='vector') FROM synthetic_vectors"
    Assert-Docker
    if ($restored -ne '3:768:0.8.2') { throw 'Restauracion sintetica incorrecta.' }
    $signatureSql = "SELECT md5(string_agg(id::text || ':' || embedding::text, ',' ORDER BY id)) FROM synthetic_vectors"
    $before = docker exec $containerId psql -X -At -v ON_ERROR_STOP=1 -U synthetic_admin -d rag93c_synthetic -c $signatureSql
    Assert-Docker
    $after = docker exec $containerId psql -X -At -v ON_ERROR_STOP=1 -U synthetic_admin -d rag93c_restored -c $signatureSql
    Assert-Docker
    if ($before -ne $after) { throw 'Contenido sintetico restaurado diferente.' }
    $cosine = docker exec $containerId psql -X -At -v ON_ERROR_STOP=1 -U synthetic_admin -d rag93c_restored -c "SELECT id FROM synthetic_vectors ORDER BY embedding <=> (SELECT embedding FROM synthetic_vectors WHERE id=1), id LIMIT 1"
    Assert-Docker
    if ($cosine -ne '1') { throw 'Coseno restaurado incorrecto.' }
    Write-Output "SYNTHETIC_RESTORE_OK $restored"
    docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' $containerId
    Assert-Docker
} finally {
    if ($containerId -match '^[0-9a-f]{64}$') {
        $labelsJson = docker inspect $containerId --format '{{json .Config.Labels}}'
        $inspectExit = $LASTEXITCODE
        $labels = $labelsJson | ConvertFrom-Json
        if ($inspectExit -ne 0 -or $labels.'app.sprint' -ne '93c-isolated') {
            throw 'No se pudo revalidar propiedad: limpieza automatica suspendida.'
        }
        docker rm -f $containerId
        Assert-Docker
    }
}
