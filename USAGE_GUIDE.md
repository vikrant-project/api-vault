# 📖 SOUL - Complete Usage Guide

## 🚀 Quick Start (3 Steps)

### Step 1: Clone and Run
```bash
git clone https://github.com/vikrant-project/api-vault.git
cd api-vault
python api-vault.py
```

### Step 2: Access the Application
Open your browser and navigate to:
```
http://localhost:9077
```

### Step 3: Create Your Account
- Click "Create Account"
- Fill in username, email, and password
- Verify OTP sent to your email
- Start using SOUL!

---

## 🎯 Complete Feature Tour

### 1. **Dashboard** (`/dashboard`)
Your central hub showing:
- **Total API Keys** - How many keys you've generated
- **Total Requests** - API calls made
- **Rate Limit Used** - Usage percentage across all keys
- **Available Modules** - 900 modules ready to use

**Quick Actions:**
- Click any stat card to navigate to related page
- Browse Modules → Go to module browser
- Manage API Keys → View/delete keys
- View Analytics → Detailed statistics

---

### 2. **Module Browser** (`/modules`)

#### Features:
✅ **Search Functionality**
- Real-time search across all 900 modules
- Search by module name
- Instant filtering as you type

✅ **Category Filtering**
- 💬 Chatbot (50 modules)
- 🎨 Text-to-Image (50 modules)
- 🖼️ Image Processing (50 modules)
- 🌍 Translation (50 modules)
- 💻 Coding Assistant (50 modules)
- 🎵 Voice/Audio (50 modules)
- 📊 Data Analysis (50 modules)
- 📝 Content Generation (50 modules)
- 👁️ Computer Vision (50 modules)

✅ **One-Click API Key Generation**
- Click "Generate API Key" on any module
- Key is displayed immediately (save it!)
- Automatic redirect to API Keys page

#### How to Use:
1. Browse or search for a module
2. Filter by category if needed
3. Click "Generate API Key" button
4. Copy and save your API key
5. Use in your application

**Example Search:**
- Search: "Sentiment" → Finds SentimentAnalyzer
- Filter: Chatbot → Shows only chatbot modules
- Combined: Search + Filter for precise results

---

### 3. **API Key Management** (`/api-keys`)

#### Features:
✅ **View All Keys**
- Module name and category
- Masked API key (security)
- Creation and last used dates
- Usage statistics (used/monthly limit)
- Visual progress bar

✅ **Usage Monitoring**
- Real-time usage tracking
- Monthly rate limits (default: 1000 requests)
- Percentage usage display
- Automatic reset date

✅ **Key Management**
- Delete keys with confirmation
- Status indicators (Active/Inactive)
- Detailed usage breakdown

#### Key Information Display:
```
Module: SentimentAnalyzer
Category: chatbot
Status: ACTIVE
API Key: API_****567890
Created: 2025-01-15
Last Used: 2025-01-16
Usage: 50/1000 (5.0%)
[█░░░░░░░░░] Progress bar
```

---

### 4. **Statistics & Analytics** (`/statistics`)

#### Overview Cards:
- **Total API Keys** - All keys (active + inactive)
- **Active Keys** - Currently usable keys
- **Total Requests** - Lifetime API calls
- **Avg Response Time** - Performance metric

#### Top 5 Most Used Modules:
- Ranked list with call counts
- Helps identify popular modules
- Optimize your usage patterns

#### Usage by Category:
- Visual bar chart
- Percentage breakdown
- Identify which categories you use most

#### Recent Activity Table:
- Last 10 API requests
- Module name
- Timestamp
- Status code (200 = success)
- Response time in milliseconds

**Use Cases:**
- Monitor performance
- Track usage patterns
- Identify bottlenecks
- Audit API calls

---

## 🔌 API Usage Examples

### Authentication Flow

#### 1. Register
```bash
curl -X POST http://localhost:9077/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "confirm_password": "SecurePass123!"
  }'
```

**Response:**
```json
{
  "message": "Registration successful. Please verify OTP sent to your email.",
  "email": "john@example.com"
}
```

#### 2. Login
```bash
curl -X POST http://localhost:9077/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email_or_username": "john@example.com",
    "password": "SecurePass123!"
  }'
```

**Response:**
```json
{
  "message": "OTP sent to your email",
  "email": "john@example.com"
}
```

#### 3. Verify OTP
```bash
curl -X POST http://localhost:9077/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "otp": "123456"
  }'
```

**Response:** Session cookie set, redirects to dashboard

---

### Working with Modules

#### 1. List All Modules
```bash
curl http://localhost:9077/api/modules/list \
  -H "Cookie: session_token=YOUR_SESSION_TOKEN"
```

**Response:**
```json
{
  "chatbot": [
    {
      "id": "chatbot_1",
      "name": "SimpleGreetingBot",
      "description": "Pattern matching for greetings",
      "category": "chatbot",
      "status": "available"
    },
    ...
  ],
  "text_to_image": [...],
  ...
}
```

#### 2. Create API Key
```bash
curl -X POST http://localhost:9077/api/keys/create \
  -H "Content-Type: application/json" \
  -H "Cookie: session_token=YOUR_SESSION_TOKEN" \
  -d '{"module_name": "SentimentAnalyzer"}'
```

**Response:**
```json
{
  "id": 1,
  "api_key": "API_ABC1234567",
  "module_name": "SentimentAnalyzer",
  "category": "chatbot",
  "created_at": "2025-01-15T10:30:00",
  "message": "API key created successfully. Save this key securely - you won't be able to see it again!"
}
```

#### 3. Execute Module (Session-Free!)
```bash
curl -X POST http://localhost:9077/api/modules/SentimentAnalyzer/execute \
  -H "X-API-Key: API_ABC1234567" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "I absolutely love this product! It exceeded all my expectations and the customer service was amazing!"
  }'
```

**Response:**
```json
{
  "module": "SentimentAnalyzer",
  "status": "success",
  "input": "I absolutely love this product! It exceeded all my expectations and the customer service was amazi",
  "output": {
    "sentiment": "positive",
    "confidence": 0.85,
    "positive_score": 3,
    "negative_score": 0
  },
  "processing_time_ms": 8,
  "rate_limit": {
    "limit": 1000,
    "used": 1,
    "remaining": 999,
    "reset_date": "2025-02-15T10:30:00"
  }
}
```

---

## 🔐 Security Features

### 1. **Encrypted Storage**
- All API keys encrypted with AES-256
- Emails and usernames encrypted
- Passwords hashed with bcrypt

### 2. **Rate Limiting**
- Authentication: 5 requests per 15 minutes
- API Keys: 1000 requests per month (configurable)
- Automatic reset on monthly cycle

### 3. **Session Management**
- 24-hour session expiry
- Secure HTTP-only cookies
- Automatic logout on inactivity

### 4. **Account Protection**
- Account lockout after 5 failed login attempts
- 1-hour lockout duration
- Email verification required

### 5. **API Key Security**
- Keys shown only once at creation
- Masked in all listings
- Deterministic hash for secure lookups

---

## 🛠️ Advanced Usage

### Custom Rate Limits

Edit `soul.py` to change per-key limits:
```python
# Default: 1000 requests/month
await cursor.execute('''
    INSERT INTO api_keys (user_id, module_name, category, api_key, api_key_hash, rate_limit_reset_date)
    VALUES (?, ?, ?, ?, ?, ?)
''', (user_id, data.module_name, module_category, encrypt_data(api_key), hash_for_lookup(api_key), reset_date))
```

Change to:
```python
# Custom: 5000 requests/month
await cursor.execute('''
    INSERT INTO api_keys (user_id, module_name, category, api_key, api_key_hash, rate_limit_monthly, rate_limit_reset_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', (user_id, data.module_name, module_category, encrypt_data(api_key), hash_for_lookup(api_key), 5000, reset_date))
```

### Session Duration

Change session expiry in `soul.py`:
```python
# Default: 24 hours
session_expiry = (datetime.now() + timedelta(hours=24)).isoformat()
max_age=86400

# Change to: 7 days
session_expiry = (datetime.now() + timedelta(days=7)).isoformat()
max_age=604800
```

### Background Installation

Check package installation status:
```bash
curl http://localhost:9077/api/health
```

**Response:**
```json
{
  "status": "ok",
  "version": "2.0.2",
  "message": "SOUL API is running (ALL BUGS FIXED)",
  "packages_installing": false,
  "packages_complete": true,
  "installed": ["fastapi", "uvicorn", "numpy", "pandas", ...],
  "pending": [],
  "failed": []
}
```

---

## 🎨 Module Categories Explained

### 💬 **Chatbot Modules** (50)
**Use Cases:** Customer support, FAQ automation, sentiment analysis

**Popular Modules:**
- `SentimentAnalyzer` - Positive/negative/neutral detection
- `IntentClassifier` - Understand user intentions
- `EntityExtractor` - Extract names, dates, locations
- `ContextAwareChat` - Multi-turn conversations
- `EmotionDetector` - Detect emotions in text

**Example:**
```bash
curl -X POST http://localhost:9077/api/modules/EmotionDetector/execute \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"input": "I am so excited about this!"}'
```

---

### 🎨 **Text-to-Image Modules** (50)
**Use Cases:** Terminal UIs, ASCII art, visual content

**Popular Modules:**
- `ASCIIArtGenerator` - Convert text to ASCII art
- `BarChartGenerator` - Text-based charts
- `ColoredTextGenerator` - ANSI color codes
- `QRCodeGenerator` - Generate QR codes
- `GradientTextGenerator` - Gradient effects

---

### 🖼️ **Image Processing Modules** (50)
**Use Cases:** Photo editing, computer vision, quality control

**Popular Modules:**
- `EdgeDetector` - Detect edges in images
- `ImageResizer` - Resize images
- `BlurFilter` - Apply blur effects
- `BrightnessAdjuster` - Adjust brightness
- `QRCodeDecoder` - Decode QR codes

---

### 🌍 **Translation Modules** (50)
**Use Cases:** International apps, documentation, customer support

**Languages Supported:**
- Spanish, French, German, Italian, Portuguese
- Chinese, Japanese, Korean, Cantonese
- Arabic, Hindi, Urdu, Bengali, Tamil
- And 35 more languages!

**Popular Modules:**
- `EnglishToSpanish` - Bidirectional translation
- `LanguageDetector` - Auto-detect language
- `EnglishToChinese` - Chinese translation
- `EnglishToArabic` - Arabic translation

---

### 💻 **Coding Assistant Modules** (50)
**Use Cases:** IDEs, code review, education

**Popular Modules:**
- `PythonCodeGenerator` - Generate Python code
- `SyntaxChecker` - Validate code syntax
- `CodeFormatter` - Format code properly
- `SecurityVulnerabilityScanner` - Find security issues
- `UnitTestGenerator` - Generate tests

---

### 🎵 **Voice/Audio Modules** (50)
**Use Cases:** Podcasting, audio processing, accessibility

**Popular Modules:**
- `TextToSpeech` - Convert text to speech
- `AudioCompressor` - Compress audio
- `NoiseGateFilter` - Remove noise
- `FrequencyAnalyzer` - Analyze frequencies
- `SpectrogramGenerator` - Visual audio representation

---

### 📊 **Data Analysis Modules** (50)
**Use Cases:** Business intelligence, research, analytics

**Popular Modules:**
- `LinearRegressionAnalyzer` - Trend analysis
- `OutlierDetector` - Find anomalies
- `CorrelationAnalyzer` - Find relationships
- `TimeSeriesAnalyzer` - Time-based analysis
- `PCADimensionalityReducer` - Reduce complexity

---

### 📝 **Content Generation Modules** (50)
**Use Cases:** Marketing, blogging, social media

**Popular Modules:**
- `ArticleGenerator` - Generate articles
- `MetaDescriptionGenerator` - SEO metadata
- `SocialMediaCaptionGenerator` - Social content
- `EmailTemplateGenerator` - Email templates
- `SummarizerModule` - Summarize text

---

### 👁️ **Computer Vision Modules** (50)
**Use Cases:** Security, healthcare, automation

**Popular Modules:**
- `FaceDetector` - Detect faces
- `ObjectDetector` - Identify objects
- `OCRTextExtractor` - Extract text from images
- `LicensePlateDetector` - Read license plates
- `QRCodeDetector` - Detect QR codes

---

## 🐛 Troubleshooting

### Issue: Module execution returns 401
**Cause:** Invalid or expired API key  
**Solution:** Generate a new API key from the modules page

### Issue: OTP email not received
**Cause:** Email service delay or spam folder  
**Solution:** Check spam folder, wait 2-3 minutes, or request new OTP

### Issue: Rate limit exceeded
**Cause:** Monthly limit reached (1000 requests)  
**Solution:** Wait for automatic reset (check reset_date) or increase limit

### Issue: Session expired
**Cause:** 24-hour session timeout  
**Solution:** Login again to create new session

### Issue: Server won't start
**Cause:** Port 9077 already in use  
**Solution:** Change port in soul.py: `uvicorn.run(app, host="0.0.0.0", port=XXXX)`

---

## 📚 Additional Resources

- **Swagger API Docs:** http://localhost:9077/docs
- **ReDoc Documentation:** http://localhost:9077/redoc
- **GitHub Repository:** https://github.com/vikrant-project/api-vault
- **Health Check:** http://localhost:9077/api/health

---

## 💡 Pro Tips

1. **Save API Keys Immediately** - They're only shown once at creation
2. **Monitor Usage Regularly** - Check statistics page to avoid rate limits
3. **Use Session-Free Execution** - Perfect for external integrations
4. **Filter Before Searching** - Narrow down category first for faster results
5. **Check Health Endpoint** - Verify server status and package installation
6. **Leverage Multiple Keys** - Create separate keys for different applications
7. **Review Recent Activity** - Audit your API usage patterns
8. **Bookmark Important Pages** - Quick access to frequently used modules

---

## 🎯 Next Steps

1. ✅ Create your account
2. ✅ Browse modules and find what you need
3. ✅ Generate API keys
4. ✅ Integrate into your application
5. ✅ Monitor usage and performance
6. ✅ Scale as needed (unlimited offline usage!)

**Welcome to SOUL - Your Complete Offline AI Infrastructure!** 🚀
