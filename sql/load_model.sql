-- ============================================================================
--  ONE-TIME: load an in-database ONNX embedding model so embeddings/retrieval
--  run entirely inside Oracle (zero external calls). Run as a user with
--  CREATE MINING MODEL (the DEBATE user already has it via DWROLE).
--
--  Oracle distributes a prebuilt, augmented all-MiniLM-L12-v2 ONNX model.
--  Get it into the database with ONE of the options below, then LOAD it.
-- ============================================================================

-- ---- Option A: load directly from cloud/object storage (no local file) -------
-- Requires a credential to the bucket holding the .onnx file (or a public PAR).
-- BEGIN
--   DBMS_VECTOR.LOAD_ONNX_MODEL_CLOUD(
--     model_name   => 'DOC_MODEL',
--     credential   => 'MY_OBJSTORE_CRED',                       -- created via DBMS_CLOUD.CREATE_CREDENTIAL
--     uri          => 'https://objectstorage.<region>.oraclecloud.com/.../all_MiniLM_L12_v2.onnx',
--     metadata     => JSON('{"function":"embedding","embeddingOutput":"embedding","input":{"input":["DATA"]}}')
--   );
-- END;
-- /

-- ---- Option B: file already staged in a directory (e.g. DATA_PUMP_DIR) --------
-- Put all_MiniLM_L12_v2.onnx in the directory first (DBMS_CLOUD.GET_OBJECT, or upload).
-- BEGIN
--   DBMS_VECTOR.LOAD_ONNX_MODEL(
--     directory  => 'DATA_PUMP_DIR',
--     file_name  => 'all_MiniLM_L12_v2.onnx',
--     model_name => 'DOC_MODEL',
--     metadata   => JSON('{"function":"embedding","embeddingOutput":"embedding","input":{"input":["DATA"]}}')
--   );
-- END;
-- /

-- ---- Verify ------------------------------------------------------------------
-- SELECT model_name, mining_function, algorithm FROM user_mining_models
--  WHERE model_name = 'DOC_MODEL';
-- SELECT VECTOR_EMBEDDING(DOC_MODEL USING 'hello world' AS data) AS v FROM dual;

-- Once DOC_MODEL exists, re-run:  python src/seed.py   (it auto-switches to in-DB mode)
-- Then:                          python src/ask.py
