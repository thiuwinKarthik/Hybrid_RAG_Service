const test = require('node:test');
const assert = require('node:assert');
const jwt = require('jsonwebtoken');
const { JWT_SECRET } = require('../src/middleware/auth');

test('JWT token creation and verification', () => {
  const user = { id: 'test-123', email: 'test@example.com', role: 'ADMIN' };
  const token = jwt.sign(user, JWT_SECRET, { expiresIn: '1h' });
  assert.ok(token);

  const decoded = jwt.verify(token, JWT_SECRET);
  assert.strictEqual(decoded.id, 'test-123');
  assert.strictEqual(decoded.role, 'ADMIN');
});
