const express = require('express');
const router = express.Router();
const multer = require('multer');
const axios = require('axios');
const FormData = require('form-data');
const { v4: uuidv4 } = require('uuid');
const { inMemoryDb, isPgConnected, pgPool } = require('../config/db');
const { authenticateToken } = require('../middleware/auth');

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 50 * 1024 * 1024 } // 50MB limit
});

const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:8000';

// GET /api/documents (List documents)
router.get('/', authenticateToken, async (req, res) => {
  let docs = [];
  if (isPgConnected()) {
    try {
      const result = await pgPool.query('SELECT * FROM documents ORDER BY upload_date DESC');
      docs = result.rows;
    } catch (e) {
      console.error(e);
    }
  }
  if (docs.length === 0) {
    docs = inMemoryDb.documents;
  }
  res.json({ documents: docs });
});

// POST /api/documents/upload (Async upload pipeline trigger)
router.post('/upload', authenticateToken, upload.single('file'), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded.' });
  }

  const { originalname, size, buffer } = req.file;
  const file_type = originalname.split('.').pop().toLowerCase();
  const strategy = req.body.strategy || 'fixed';
  const documentId = uuidv4();

  const docRecord = {
    id: documentId,
    filename: originalname,
    file_type,
    file_size: size,
    uploaded_by: req.user.id,
    upload_date: new Date(),
    status: 'PROCESSING',
    version: 1,
    processing_time: 0,
    chunk_count: 0,
    error_message: null
  };

  if (isPgConnected()) {
    try {
      await pgPool.query(
        `INSERT INTO documents (id, filename, file_type, file_size, uploaded_by, status)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [documentId, originalname, file_type, size, req.user.id, 'PROCESSING']
      );
    } catch (e) {
      console.error('Error inserting document:', e);
    }
  }
  inMemoryDb.documents.unshift(docRecord);

  // Return asynchronous confirmation immediately
  res.status(202).json({
    message: 'Document upload received and queued for asynchronous processing.',
    documentId,
    status: 'PROCESSING',
    filename: originalname
  });

  // Asynchronous Background Worker dispatch to FastAPI Microservice
  (async () => {
    try {
      const formData = new FormData();
      formData.append('file', buffer, originalname);
      formData.append('document_id', documentId);
      formData.append('strategy', strategy);

      // Call Python RAG service /ingest/process
      const response = await axios.post(`${RAG_SERVICE_URL}/ingest/process`, formData, {
        headers: formData.getHeaders(),
        timeout: 120000
      });

      const { chunk_count, processing_time_sec } = response.data;

      // Update status to COMPLETED
      docRecord.status = 'COMPLETED';
      docRecord.chunk_count = chunk_count;
      docRecord.processing_time = processing_time_sec;

      const { saveDocumentsToDisk } = require('../config/db');
      saveDocumentsToDisk();

      if (isPgConnected()) {
        await pgPool.query(
          `UPDATE documents SET status = 'COMPLETED', chunk_count = $1, processing_time = $2 WHERE id = $3`,
          [chunk_count, processing_time_sec, documentId]
        );
      }
      console.log(`[Ingestion Complete] Document ${originalname} (${documentId}) -> ${chunk_count} chunks.`);

      // Clear query cache on new document ingestion
      inMemoryDb.query_cache.clear();

    } catch (err) {
      console.error(`[Ingestion Failed] Document ${documentId}:`, err.message);
      docRecord.status = 'FAILED';
      docRecord.error_message = err.message;
      const { saveDocumentsToDisk } = require('../config/db');
      saveDocumentsToDisk();
      if (isPgConnected()) {
        await pgPool.query(
          `UPDATE documents SET status = 'FAILED', error_message = $1 WHERE id = $2`,
          [err.message, documentId]
        );
      }
    }
  })();
});

// DELETE /api/documents/:id (Delete document)
router.delete('/:id', authenticateToken, async (req, res) => {
  const docId = req.params.id;

  try {
    await axios.delete(`${RAG_SERVICE_URL}/ingest/documents/${docId}`);
  } catch (e) {
    console.warn(`[RAG Service Delete Warning] ${e.message}`);
  }

  if (isPgConnected()) {
    try {
      await pgPool.query('DELETE FROM documents WHERE id = $1', [docId]);
    } catch (e) {
      console.error(e);
    }
  }

  inMemoryDb.documents = inMemoryDb.documents.filter(d => d.id !== docId);
  const { saveDocumentsToDisk } = require('../config/db');
  saveDocumentsToDisk();
  inMemoryDb.query_cache.clear();

  res.json({ message: 'Document deleted successfully.', documentId: docId });
});


module.exports = router;
