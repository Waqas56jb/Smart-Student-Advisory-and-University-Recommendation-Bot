const express = require('express');
const mysql = require('mysql2/promise');
const bcrypt = require('bcrypt');
const nodemailer = require('nodemailer');
const crypto = require('crypto');
const app = express();
const port = 3000;

app.use(express.json());
app.use(express.static('public')); // Serve static files (HTML, CSS, JS)

const dbConfig = {
    host: 'localhost',
    user: 'root', // Change to your MySQL username
    password: 'your_password', // Change to your MySQL password
    database: 'edupath_auth'
};

let pool;

async function initializeDB() {
    pool = await mysql.createPool(dbConfig);
    console.log('MySQL connected');
}

initializeDB().catch(err => console.error('Database connection failed:', err));

// Nodemailer setup for email
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: 'your_email@gmail.com', // Your Gmail
        pass: 'your_app_password' // App-specific password for Gmail
    }
});

app.post('/signup', async (req, res) => {
    const { username, email, password } = req.body;
    try {
        const hashedPassword = await bcrypt.hash(password, 10);
        const [result] = await pool.query(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            [username, email, hashedPassword]
        );
        res.json({ success: true, message: 'User registered successfully' });
    } catch (err) {
        if (err.code === 'ER_DUP_ENTRY') {
            res.json({ success: false, message: 'Email or username already exists' });
        } else {
            res.status(500).json({ success: false, message: 'Server error' });
        }
    }
});

app.post('/login', async (req, res) => {
    const { email, password } = req.body;
    try {
        const [rows] = await pool.query('SELECT * FROM users WHERE email = ?', [email]);
        if (rows.length > 0) {
            const user = rows[0];
            const match = await bcrypt.compare(password, user.password);
            if (match) {
                res.json({ success: true, message: 'Login successful' });
            } else {
                res.json({ success: false, message: 'Incorrect password' });
            }
        } else {
            res.json({ success: false, message: 'User not found' });
        }
    } catch (err) {
        res.status(500).json({ success: false, message: 'Server error' });
    }
});

app.post('/forget-password', async (req, res) => {
    const { email } = req.body;
    try {
        const [rows] = await pool.query('SELECT * FROM users WHERE email = ?', [email]);
        if (rows.length > 0) {
            const token = crypto.randomBytes(20).toString('hex');
            const expiresAt = new Date(Date.now() + 3600000); // 1 hour from now

            await pool.query(
                'INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)',
                [email, token, expiresAt]
            );

            const resetLink = `http://localhost:3000/reset-password?token=${token}`;
            const mailOptions = {
                from: 'your_email@gmail.com',
                to: email,
                subject: 'Password Reset Request',
                text: `Click the following link to reset your password: ${resetLink}`
            };

            await transporter.sendMail(mailOptions);
            res.json({ success: true, message: 'Password reset link sent' });
        } else {
            res.json({ success: false, message: 'Email not found' });
        }
    } catch (err) {
        res.status(500).json({ success: false, message: 'Server error' });
    }
});

app.get('/reset-password', async (req, res) => {
    const { token } = req.query;
    try {
        const [rows] = await pool.query('SELECT * FROM password_resets WHERE token = ? AND expires_at > NOW()', [token]);
        if (rows.length > 0) {
            res.send(`
                <!DOCTYPE html>
                <html>
                <head><title>Reset Password</title></head>
                <body>
                    <form action="/reset-password" method="post">
                        <input type="hidden" name="token" value="${token}">
                        <input type="password" name="newPassword" placeholder="New Password" required><br>
                        <input type="password" name="confirmPassword" placeholder="Confirm Password" required><br>
                        <button type="submit">Reset Password</button>
                    </form>
                </body>
                </html>
            `);
        } else {
            res.send('Invalid or expired token');
        }
    } catch (err) {
        res.status(500).send('Server error');
    }
});

app.post('/reset-password', async (req, res) => {
    const { token, newPassword, confirmPassword } = req.body;
    if (newPassword !== confirmPassword) {
        return res.status(400).send('Passwords do not match');
    }
    try {
        const [rows] = await pool.query('SELECT * FROM password_resets WHERE token = ? AND expires_at > NOW()', [token]);
        if (rows.length > 0) {
            const hashedPassword = await bcrypt.hash(newPassword, 10);
            await pool.query('UPDATE users SET password = ? WHERE email = ?', [hashedPassword, rows[0].email]);
            await pool.query('DELETE FROM password_resets WHERE token = ?', [token]);
            res.send('Password reset successful. <a href="login.html">Login</a>');
        } else {
            res.send('Invalid or expired token');
        }
    } catch (err) {
        res.status(500).send('Server error');
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});