const express = require('express');
const mysql = require('mysql2');
const bodyParser = require('body-parser');

const app = express();
const port = 3000;

// Database Connection
const db = mysql.createConnection({
  host: '127.0.0.1',
  port: 3306,
  user: 'root',
  password: '1234', // Empty password as per screenshot
  database: 'edupath_auth'
});

db.connect((err) => {
  if (err) {
    console.error('Database connection failed:', err.stack);
    return;
  }
  console.log('Connected to database.');
});

// Middleware
app.use(bodyParser.json());
app.use(express.static('public')); // Serve static files (HTML)

// Signup Endpoint
app.post('/signup', (req, res) => {
  const { username, email, password, confirmPassword } = req.body;

  if (password !== confirmPassword) {
    return res.status(400).json({ message: 'Passwords do not match' });
  }

  const checkEmailQuery = 'SELECT email FROM users WHERE email = ?';
  db.query(checkEmailQuery, [email], (err, results) => {
    if (err) return res.status(500).json({ message: 'Database error' });
    if (results.length > 0) {
      return res.status(400).json({ message: 'Email already exists' });
    }

    const insertQuery = 'INSERT INTO users (username, email, password) VALUES (?, ?, ?)';
    db.query(insertQuery, [username, email, password], (err) => {
      if (err) return res.status(500).json({ message: 'Signup failed' });
      res.status(201).json({ message: 'Signup successful' });
    });
  });
});

// Login Endpoint
app.post('/login', (req, res) => {
  const { email, password } = req.body;

  const query = 'SELECT * FROM users WHERE email = ? AND password = ?';
  db.query(query, [email, password], (err, results) => {
    if (err) return res.status(500).json({ message: 'Database error' });
    if (results.length === 0) {
      return res.status(400).json({ message: 'Invalid email or password' });
    }
    res.status(200).json({ message: 'Login successful' });
  });
});

// Forget Password Endpoint
app.post('/forget-password', (req, res) => {
  const { email } = req.body;

  const checkEmailQuery = 'SELECT email FROM users WHERE email = ?';
  db.query(checkEmailQuery, [email], (err, results) => {
    if (err) return res.status(500).json({ message: 'Database error' });
    if (results.length === 0) {
      return res.status(400).json({ message: 'Email does not exist' });
    }

    const token = Math.random().toString(36).substring(2, 15);
    const expiresAt = new Date(Date.now() + 3600000); // 1 hour expiry
    const insertResetQuery = 'INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)';
    db.query(insertResetQuery, [email, token, expiresAt], (err) => {
      if (err) return res.status(500).json({ message: 'Failed to initiate reset' });
      res.status(200).json({ message: 'Reset token generated', token });
    });
  });
});

// Reset Password Endpoint
app.post('/reset-password', (req, res) => {
  const { token, newPassword, confirmPassword } = req.body;

  if (newPassword !== confirmPassword) {
    return res.status(400).json({ message: 'Passwords do not match' });
  }

  const checkTokenQuery = 'SELECT email FROM password_resets WHERE token = ? AND expires_at > NOW()';
  db.query(checkTokenQuery, [token], (err, results) => {
    if (err) return res.status(500).json({ message: 'Database error' });
    if (results.length === 0) {
      return res.status(400).json({ message: 'Invalid or expired token' });
    }

    const email = results[0].email;
    const updateQuery = 'UPDATE users SET password = ? WHERE email = ?';
    db.query(updateQuery, [newPassword, email], (err) => {
      if (err) return res.status(500).json({ message: 'Password reset failed' });
      const deleteQuery = 'DELETE FROM password_resets WHERE token = ?';
      db.query(deleteQuery, [token], (err) => {
        if (err) console.error('Failed to delete token:', err);
      });
      res.status(200).json({ message: 'Password reset successful' });
    });
  });
});

// Serve HTML files
app.get('/login', (req, res) => res.sendFile(__dirname + '/public/login.html'));
app.get('/signup', (req, res) => res.sendFile(__dirname + '/public/signup.html'));
app.get('/forget-password', (req, res) => res.sendFile(__dirname + '/public/forget-password.html'));

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});