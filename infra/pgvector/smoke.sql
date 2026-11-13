\set ON_ERROR_STOP on
-- Exclusivamente base ficticia, nunca desarrollo/pruebas del proyecto.
DO $$ BEGIN
 IF current_database() <> 'rag93c_synthetic' THEN
  RAISE EXCEPTION 'Destino no permitido';
 END IF;
 IF current_setting('server_version_num')::int / 10000 <> 18 THEN
  RAISE EXCEPTION 'Version mayor incorrecta';
 END IF;
END $$;
CREATE EXTENSION vector VERSION '0.8.2';
CREATE TABLE synthetic_vectors(id integer PRIMARY KEY, embedding vector(768) NOT NULL);
INSERT INTO synthetic_vectors
SELECT id, ARRAY(SELECT CASE WHEN n=id THEN 1.0 ELSE 0.0 END FROM generate_series(1,768) n)::vector
FROM generate_series(1,3) id;
DO $$ DECLARE q vector(768); nearest integer; distance double precision;
BEGIN
 SELECT embedding INTO q FROM synthetic_vectors WHERE id=1;
 SELECT id, embedding <=> q INTO nearest, distance
 FROM synthetic_vectors ORDER BY embedding <=> q, id LIMIT 1;
 IF nearest <> 1 OR abs(distance) > 1e-6 THEN RAISE EXCEPTION 'Coseno identidad incorrecto'; END IF;
 SELECT embedding <=> q INTO distance FROM synthetic_vectors WHERE id=2;
 IF abs(distance-1) > 1e-6 THEN RAISE EXCEPTION 'Coseno ortogonal incorrecto'; END IF;
 BEGIN
  INSERT INTO synthetic_vectors VALUES (4, '[1,0]'::vector);
  RAISE EXCEPTION 'No se rechazo dimension incorrecta';
 EXCEPTION WHEN data_exception THEN NULL;
 END;
 IF (SELECT count(*) FROM synthetic_vectors) <> 3 THEN RAISE EXCEPTION 'Conteo incorrecto'; END IF;
END $$;
SELECT current_database(), current_setting('server_version'), extversion
FROM pg_extension WHERE extname='vector';
SELECT 'SYNTHETIC_VECTOR_CHECKS_OK' AS result;
