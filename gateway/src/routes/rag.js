const express = require('express');
const router = express.Router();
const axios = require('axios');
const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');
const { inMemoryDb, isPgConnected, pgPool } = require('../config/db');
const { authenticateToken } = require('../middleware/auth');

const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:8000';

// Helper for caching
const getQueryHash = (query, retrievalMode) => {
  return crypto.createHash('sha256').update(`${query.trim().toLowerCase()}_${retrievalMode}`).digest('hex');
};

// POST /api/rag/query (Ask natural language question)
router.post('/query', authenticateToken, async (req, res) => {
  const { query, conversation_id, retrieval_mode = 'hybrid', top_k = 10 } = req.body;

  if (!query || !query.trim()) {
    return res.status(400).json({ error: 'Query text is required.' });
  }

  // Check Cache (Module 22)
  const cacheKey = getQueryHash(query, retrieval_mode);
  if (inMemoryDb.query_cache.has(cacheKey)) {
    const cachedResponse = inMemoryDb.query_cache.get(cacheKey);
    return res.json({
      ...cachedResponse,
      cached: true
    });
  }

  try {
    const ragResponse = await axios.post(`${RAG_SERVICE_URL}/rag/query`, {
      query,
      retrieval_mode,
      top_k
    });

    const responseData = ragResponse.data;

    // Cache valid response
    inMemoryDb.query_cache.set(cacheKey, responseData);

    // Save message to conversation if conversation_id provided
    if (conversation_id) {
      const msgId = uuidv4();
      const msgRecord = {
        id: msgId,
        conversation_id,
        sender: 'assistant',
        query,
        answer: responseData.answer,
        citations: responseData.citations,
        confidence_score: responseData.confidence_score,
        execution_time_ms: responseData.execution_time_ms,
        created_at: new Date()
      };
      inMemoryDb.messages.push(msgRecord);
    }

    res.json({
      ...responseData,
      cached: false
    });
  } catch (err) {
    console.error('RAG Service Query Error:', err.message);
    res.status(500).json({
      error: 'Failed to process RAG query.',
      details: err.response?.data || err.message
    });
  }
});

// GET /api/rag/conversations (Get user conversations)
router.get('/conversations', authenticateToken, async (req, res) => {
  const userId = req.user.id;
  let convs = inMemoryDb.conversations.filter(c => c.user_id === userId);
  res.json({ conversations: convs });
});

// POST /api/rag/conversations (Create new conversation)
router.post('/conversations', authenticateToken, async (req, res) => {
  const userId = req.user.id;
  const { title = 'New Conversation' } = req.body;
  const newConv = {
    id: uuidv4(),
    user_id: userId,
    title,
    created_at: new Date(),
    updated_at: new Date()
  };
  inMemoryDb.conversations.unshift(newConv);
  res.status(201).json({ conversation: newConv });
});

module.exports = router;
