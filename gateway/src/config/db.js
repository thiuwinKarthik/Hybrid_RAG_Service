const { Pool } = require('pg');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

const STORE_PATH = path.join(__dirname, '../../../database/documents_store.json');

const pgPool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: parseInt(process.env.POSTGRES_PORT || '5432'),
  database: process.env.POSTGRES_DB || 'rag_enterprise',
  user: process.env.POSTGRES_USER || 'rag_admin',
  password: process.env.POSTGRES_PASSWORD || 'rag_secure_password_2026',
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
});

// Load persistent disk store fallback
let initialDocs = [];
try {
  if (fs.existsSync(STORE_PATH)) {
    const data = fs.readFileSync(STORE_PATH, 'utf8');
    initialDocs = JSON.parse(data);
    console.log(`[DocumentStore] Hydrated ${initialDocs.length} persistent documents from disk store.`);
  }
} catch (e) {
  console.error('[DocumentStore] Disk store load error:', e.message);
}

const inMemoryDb = {
  users: [
    {
      id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
      email: 'admin@enterprise-rag.com',
      password_hash: '$2a$10$E.0aA1rL9z6f7qB4G1u4g.hQ4b.z2h7W8m1k9x3v5c2b4n6m8k0j2', // Admin123!
      full_name: 'Enterprise Admin',
      role: 'ADMIN'
    },
    {
      id: 'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
      email: 'employee@enterprise-rag.com',
      password_hash: '$2a$10$E.0aA1rL9z6f7qB4G1u4g.hQ4b.z2h7W8m1k9x3v5c2b4n6m8k0j2', // Admin123!
      full_name: 'Standard Employee',
      role: 'EMPLOYEE'
    }
  ],
  documents: initialDocs,
  document_chunks: [],
  conversations: [],
  messages: [],
  query_cache: new Map()
};

const saveDocumentsToDisk = () => {
  try {
    const dir = path.dirname(STORE_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(STORE_PATH, JSON.stringify(inMemoryDb.documents, null, 2), 'utf8');
  } catch (e) {
    console.error('[DocumentStore] Save disk store error:', e.message);
  }
};

let isPgConnected = false;

pgPool.connect((err, client, release) => {
  if (err) {
    console.log('[PostgreSQL] Database connection unavailable:', err.message, '- Using persistent file storage manager.');
    isPgConnected = false;
  } else {
    console.log('[PostgreSQL] Database pool connected successfully.');
    isPgConnected = true;
    release();
  }
});

module.exports = {
  pgPool,
  inMemoryDb,
  saveDocumentsToDisk,
  isPgConnected: () => isPgConnected,
  query: async (text, params) => {
    if (isPgConnected) {
      try {
        return await pgPool.query(text, params);
      } catch (e) {
        console.error('[PostgreSQL Error]', e.message);
      }
    }
    return { rows: [] };
  }
};
