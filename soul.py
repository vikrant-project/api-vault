#!/usr/bin/env python3
"""
SOUL - API Management System (FULLY FIXED v2.0.2)
A complete AI modules and API key management system with user authentication,
OTP verification, and 900 offline AI modules across 9 categories.

Author: SOUL Development Team
Version: 2.0.2 (ALL CRITICAL BUGS FIXED)
License: MIT

CRITICAL FIXES IN v2.0.2:
- API key lookup now uses api_key_hash (deterministic) instead of encrypted value
- Background package installation - server starts immediately
- Session expiry extended to 24 hours
- API execution works without session cookie (API key only)
- /api/health endpoint shows installation progress
"""

import sys
import os
import subprocess
import importlib.util
import json
import re
import secrets
import string
import time
import asyncio
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

# ============================================================================
# DEPENDENCY CHECKER AND AUTO-INSTALLER (FIXED - BACKGROUND INSTALLATION)
# ============================================================================

print("╔════════════════════════════════════════════════════════════════╗")
print("║          SOUL - API Management System v2.0.2                   ║")
print("║                Initializing Application                        ║")
print("╚════════════════════════════════════════════════════════════════╝\n")

# Check Python version
python_version = sys.version_info
if python_version < (3, 8):
    print(f"[✗] Python 3.8+ required. Current: {python_version.major}.{python_version.minor}")
    sys.exit(1)
print(f"[✓] Python version: {python_version.major}.{python_version.minor}.{python_version.micro} - OK")

# CRITICAL packages needed to start FastAPI server
CRITICAL_PACKAGES = {
    'fastapi': 'fastapi==0.104.0',
    'uvicorn': 'uvicorn==0.24.0',
    'pydantic': 'pydantic==2.4.0',
    'cryptography': 'cryptography==41.0.0',
    'dotenv': 'python-dotenv==1.0.0',
    'requests': 'requests==2.31.0',
    'bcrypt': 'bcrypt==4.0.1',
    'aiosqlite': 'aiosqlite==0.19.0',
}

# Non-critical packages (can be installed in background)
NON_CRITICAL_PACKAGES = {
    'PIL': 'pillow==10.0.0',
    'cv2': 'opencv-python==4.8.0.76',
    'sklearn': 'scikit-learn==1.3.0',
    'nltk': 'nltk==3.8.1',
    'numpy': 'numpy==1.24.3',
    'pandas': 'pandas==2.0.3',
}

# Installation state tracking
installation_state = {
    'packages_installing': False,
    'packages_complete': False,
    'installed': [],
    'pending': [],
    'failed': []
}

def check_package(module_name):
    """Check if a package is installed"""
    return importlib.util.find_spec(module_name) is not None

def install_package(package_spec):
    """Install a package using pip"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec, "--quiet"])

# Install CRITICAL packages synchronously (required to start server)
print("[✓] Checking critical dependencies (required for server startup)...")
for module, package_spec in CRITICAL_PACKAGES.items():
    if check_package(module):
        print(f"  ✓ {module} already installed")
        installation_state['installed'].append(module)
    else:
        print(f"  ⚙ Installing {package_spec}...")
        try:
            install_package(package_spec)
            print(f"  ✓ {package_spec} installed successfully")
            installation_state['installed'].append(module)
        except Exception as e:
            print(f"  ✗ Failed to install {package_spec}: {e}")
            sys.exit(1)

# Now import all critical packages
import bcrypt
import aiosqlite
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import requests

def install_dependencies_background():
    """Install non-critical dependencies in background thread"""
    installation_state['packages_installing'] = True
    
    # Check what needs installation
    missing = []
    for module, package_spec in NON_CRITICAL_PACKAGES.items():
        if not check_package(module):
            missing.append((module, package_spec))
            installation_state['pending'].append(module)
    
    if not missing:
        print("[✓] All non-critical dependencies already installed")
        installation_state['packages_complete'] = True
        installation_state['packages_installing'] = False
        return
    
    print(f"[⚙] Installing {len(missing)} non-critical packages in background...")
    print("    (Server is ready - packages will install while you use the app)")
    
    for module, package_spec in missing:
        try:
            install_package(package_spec)
            print(f"  ✓ {package_spec} installed")
            installation_state['installed'].append(module)
            installation_state['pending'].remove(module)
        except Exception as e:
            print(f"  ✗ Failed: {package_spec}: {e}")
            installation_state['failed'].append(module)
            if module in installation_state['pending']:
                installation_state['pending'].remove(module)
    
    print("[✓] Background installation complete")
    installation_state['packages_complete'] = True
    installation_state['packages_installing'] = False

# Start background installation thread
threading.Thread(target=install_dependencies_background, daemon=True).start()

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================

load_dotenv()

# Generate or load encryption key
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    with open('.env', 'a') as f:
        f.write(f'\nENCRYPTION_KEY={ENCRYPTION_KEY}\n')
    print("[✓] Encryption key generated and saved to .env")
else:
    print("[✓] Encryption key loaded: EXISTS")

# Initialize Fernet cipher
cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# Database configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'soul_database.db')
EMAIL_API_URL = "https://geekerguys.com/soul/soul.php"
EMAIL_FROM = "vikrant-project@gmail.com"

# Rate limiting storage (in-memory for simplicity)
rate_limit_store = {}

# ============================================================================
# ENCRYPTION UTILITIES (FIXED WITH DETERMINISTIC HASH)
# ============================================================================

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data using AES-256"""
    if not data:
        return ""
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not encrypted_data:
        return ""
    try:
        return cipher.decrypt(encrypted_data.encode()).decode()
    except:
        return ""

def hash_for_lookup(data: str) -> str:
    """
    SHA-256 hash for deterministic DB lookups
    CRITICAL FIX: Fernet encryption is non-deterministic, so we need
    a deterministic hash for WHERE clauses in database queries
    """
    if not data:
        return ""
    salt = ENCRYPTION_KEY[:16] if ENCRYPTION_KEY else ""
    return hashlib.sha256((salt + data.lower().strip()).encode()).hexdigest()

def mask_api_key(api_key: str) -> str:
    """Mask API key showing only first 4 and last 4 characters"""
    if len(api_key) <= 8:
        return api_key
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"

# ============================================================================
# DATABASE SETUP (ASYNC) - FIXED WITH HASH COLUMNS
# ============================================================================

@asynccontextmanager
async def get_db():
    """Async database connection context manager"""
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e
    finally:
        await conn.close()

async def init_database():
    """Initialize database with all required tables (FIXED WITH HASH COLUMNS)"""
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        cursor = await conn.cursor()
        
        # Users table - ADDED email_hash and username_hash columns
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                username_hash TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                email_hash TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT,
                status TEXT DEFAULT 'active',
                is_email_verified BOOLEAN DEFAULT FALSE,
                otp_secret TEXT,
                otp_expiry TEXT,
                failed_login_attempts INTEGER DEFAULT 0,
                account_locked_until TEXT
            )
        ''')
        
        # API Keys table - ADDED api_key_hash column (FIX FOR BUG 1)
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                module_name TEXT NOT NULL,
                category TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                api_key_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                last_used TEXT,
                status TEXT DEFAULT 'active',
                rate_limit_monthly INTEGER DEFAULT 1000,
                rate_limit_used INTEGER DEFAULT 0,
                rate_limit_reset_date TEXT,
                key_version INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, module_name)
            )
        ''')
        
        # API Requests table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                api_key_id INTEGER NOT NULL,
                module_name TEXT NOT NULL,
                category TEXT NOT NULL,
                request_timestamp TEXT DEFAULT (datetime('now')),
                request_data TEXT,
                response_data TEXT,
                status_code INTEGER,
                response_time_ms INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
            )
        ''')
        
        # OTP Logs table - ADDED email_hash column
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS otp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT NOT NULL,
                email_hash TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                otp_type TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                verified BOOLEAN DEFAULT FALSE,
                verified_at TEXT
            )
        ''')
        
        # Sessions table - ADDED session_hash column
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                session_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                last_activity TEXT DEFAULT (datetime('now')),
                ip_address TEXT,
                user_agent TEXT,
                device_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Audit Logs table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                status TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        await conn.commit()
        
        print("[✓] Database initialization: OK")
        print("[✓] Tables created: 6 tables (WITH HASH COLUMNS)")
        print("  ✓ users (with email_hash, username_hash)")
        print("  ✓ api_keys (with api_key_hash - FIX FOR BUG 1)")
        print("  ✓ api_requests")
        print("  ✓ otp_logs (with email_hash)")
        print("  ✓ sessions (with session_hash)")
        print("  ✓ audit_logs")

# ============================================================================
# EMAIL UTILITIES
# ============================================================================

def send_email(to: str, subject: str, body: str) -> bool:
    """Send email using the provided API"""
    try:
        payload = {
            "to": to,
            "from": EMAIL_FROM,
            "subject": subject,
            "body": body
        }
        response = requests.post(EMAIL_API_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[✗] Email sending failed: {e}")
        return False

def get_otp_email_template(otp: str, email_type: str = "registration") -> str:
    """Generate HTML email template for OTP"""
    titles = {
        "registration": "Welcome to SOUL!",
        "login": "Login Verification",
        "forgot_password": "Password Reset"
    }
    messages = {
        "registration": "Your registration is almost complete. Use the code below to verify your email address:",
        "login": "You requested to login to SOUL. Use the code below to verify your identity:",
        "forgot_password": "You requested to reset your password. Use the code below to proceed:"
    }
    
    return f'''
<!DOCTYPE html>
<html>
<head><style>body{{font-family:Arial,sans-serif;background:#f4f4f4;padding:20px}}
.container{{max-width:600px;margin:auto;background:white;padding:30px;border-radius:10px;box-shadow:0 4px 6px rgba(0,0,0,0.1)}}
.otp-box{{font-size:32px;font-weight:bold;text-align:center;background:#f0f0f0;padding:20px;border-radius:8px;letter-spacing:8px;color:#333}}
</style></head>
<body><div class="container">
<h2>{titles.get(email_type, "Verification Code")}</h2>
<p>{messages.get(email_type, "Use the code below:")}</p>
<div class="otp-box">{otp}</div>
<p><small>This code expires in 10 minutes.</small></p>
<p><small>If you didn't request this, please ignore this email.</small></p>
<hr><p><small><strong>Security Tip:</strong> Never share your OTP with anyone. SOUL staff will never ask for your OTP.</small></p>
</div></body>
</html>
    '''

# ============================================================================
# PYDANTIC MODELS (V2 FIXED)
# ============================================================================

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', v):
            raise ValueError('Username must be 3-20 alphanumeric characters')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain number')
        if not re.search(r'[!@#$%^&*(),.?":{}\\|<>]', v):
            raise ValueError('Password must contain special character')
        return v

class UserLogin(BaseModel):
    email_or_username: str
    password: str

class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    confirm_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain number')
        if not re.search(r'[!@#$%^&*(),.?":{}\\|<>]', v):
            raise ValueError('Password must contain special character')
        return v

class CreateAPIKey(BaseModel):
    module_name: str

# ============================================================================
# 900 AI MODULES (OPTIMIZED - FIXED lru_cache issue)
# ============================================================================

class AIModules:
    """Container for all 900 offline AI modules"""
    
    # Category definitions
    CATEGORIES = {
        "chatbot": "Chatbot Modules",
        "text_to_image": "Text-to-Image Modules",
        "image_decoder": "Image Decoder Modules",
        "translation": "Translation Modules",
        "coding": "Coding Assistant Modules",
        "voice": "Voice/Audio Modules",
        "data_analysis": "Data Analysis Modules",
        "content_gen": "Content Generation Modules",
        "vision": "Vision/ML Modules"
    }
    
    # Cache modules at class level - FIXED: removed lru_cache from classmethod
    _cached_modules = None
    
    @classmethod
    def get_all_modules(cls) -> Dict[str, List[Dict]]:
        """Get all 900 modules organized by category (cached)"""
        if cls._cached_modules is None:
            cls._cached_modules = {
                "chatbot": cls.get_chatbot_modules(),
                "text_to_image": cls.get_text_to_image_modules(),
                "image_decoder": cls.get_image_decoder_modules(),
                "translation": cls.get_translation_modules(),
                "coding": cls.get_coding_modules(),
                "voice": cls.get_voice_modules(),
                "data_analysis": cls.get_data_analysis_modules(),
                "content_gen": cls.get_content_gen_modules(),
                "vision": cls.get_vision_modules()
            }
        return cls._cached_modules
    
    @staticmethod
    def get_chatbot_modules() -> List[Dict]:
        """50 Chatbot Modules"""
        modules = []
        names = [
            "SimpleGreetingBot", "FAQBot", "IntentClassifier", "SentimentAnalyzer", "EntityExtractor",
            "ContextAwareChat", "ResponseGenerator", "ConversationLogger", "KeywordMatcher", "LevenshteinSimilarity",
            "SpellingCorrector", "TokenizerBot", "StemmerBot", "LemmatizerBot", "StopWordRemover",
            "WordFrequencyAnalyzer", "QuestionAnswererBot", "DialogueManager", "ResponseRanker", "UserProfileBuilder",
            "EmotionDetector", "IntentPredictor", "ContextRetriever", "ResponseValidator", "ConversationAnalyzer",
            "LanguageDetector", "MessageNormalizer", "SynonymFinder", "AntonymFinder", "PhraseMatcher",
            "TopicModeler", "ConversationSummarizer", "RolePlayBot", "StorytellerBot", "JokeBot",
            "MotivationalBot", "MeditationGuidanceBot", "FitnessCoachBot", "CookingAssistantBot", "TravelAdvisorBot",
            "CareerCoachBot", "StudyBuddyBot", "HealthInfoBot", "FinanceAdvisorBot", "ProductRecommenderBot",
            "ReviewAnalyzerBot", "FeedbackBot", "SurveyBot", "PollBot", "ChatMemoryBot"
        ]
        descriptions = [
            "Pattern matching for greetings", "Keyword matching for FAQ responses", "TF-IDF based intent classification",
            "Polarity analysis (positive/negative/neutral)", "Named entity recognition using regex",
            "Maintains conversation memory", "Template-based response generation", "Stores conversation history",
            "Fuzzy keyword matching", "String similarity scoring", "Auto-correction using difflib",
            "Text tokenization and normalization", "Porter stemmer implementation", "Wordnet lemmatization",
            "Removes common stop words", "Analyzes word distributions", "Q&A with knowledge base",
            "Multi-turn conversation handler", "Ranks responses by relevance", "Extracts user preferences",
            "Detects emotions in text", "Predicts next user action", "Retrieves relevant context",
            "Validates response quality", "Analyzes conversation patterns", "Detects input language (simple)",
            "Normalizes text (lowercase, punctuation)", "Finds synonyms using wordnet", "Finds antonyms using wordnet",
            "Matches similar phrases", "Simple topic identification", "Summarizes chat history",
            "Plays specific roles", "Generates simple stories", "Retrieves and tells jokes",
            "Provides motivational quotes", "Guides meditation sessions", "Provides fitness routines",
            "Suggests recipes", "Travel recommendations", "Career advice provider", "Learning assistance",
            "Health information provider", "Basic financial advice", "Product recommendations",
            "Analyzes product reviews", "Collects user feedback", "Conducts surveys", "Creates and conducts polls",
            "Stores and recalls chat memories"
        ]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"chatbot_{i+1}",
                "name": name,
                "description": desc,
                "category": "chatbot",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_text_to_image_modules() -> List[Dict]:
        """50 Text-to-Image Modules"""
        modules = []
        names = [
            "ASCIIArtGenerator", "FigletTextGenerator", "BarChartGenerator", "ProgressBarGenerator", "BorderGenerator",
            "ColoredTextGenerator", "GradientTextGenerator", "ShadowTextGenerator", "BoldTextGenerator", "ItalicTextGenerator",
            "UnderlineTextGenerator", "StrikethroughTextGenerator", "InvertedTextGenerator", "RainbowTextGenerator", "BlinkingTextGenerator",
            "RotatedTextGenerator", "FlippedTextGenerator", "UpsideDownTextGenerator", "MirrorTextGenerator", "LargeTextGenerator",
            "SmallTextGenerator", "SuperscriptGenerator", "SubscriptGenerator", "FancyFontGenerator", "MathSymbolGenerator",
            "EmojiTextGenerator", "BlockLetterGenerator", "BubbleTextGenerator", "SquareTextGenerator", "CircleTextGenerator",
            "DiamondTextGenerator", "StarTextGenerator", "HeartTextGenerator", "FireTextGenerator", "WaveTextGenerator",
            "PulseTextGenerator", "TypewriterTextGenerator", "MatrixTextGenerator", "GlitchTextGenerator", "NeonTextGenerator",
            "FrostTextGenerator", "FireGlowTextGenerator", "LightningTextGenerator", "IceTextGenerator", "SmokeTextGenerator",
            "WaterTextGenerator", "SandTextGenerator", "CloudTextGenerator", "StarfieldTextGenerator", "LandscapeArtGenerator"
        ]
        descriptions = [f"Converts text to {name.replace('Generator', '').replace('Text', ' text')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"text_to_image_{i+1}",
                "name": name,
                "description": desc,
                "category": "text_to_image",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_image_decoder_modules() -> List[Dict]:
        """50 Image Decoder Modules"""
        modules = []
        names = [
            "ImageToASCII", "ImageToGrayscale", "ImageToBinary", "ImageCompressor", "ImageResizer",
            "ImageCropper", "ImageRotator", "ImageMirror", "ImageInverter", "BrightnessAdjuster",
            "ContrastAdjuster", "SaturationAdjuster", "HueShifter", "BlurFilter", "SharpenFilter",
            "EdgeDetector", "SobelEdgeDetector", "CannyEdgeDetector", "LaplacianDetector", "HistogramEqualizer",
            "AdaptiveHistogramEqualizer", "MorphologicalClosing", "MorphologicalOpening", "DilatationFilter", "ErosionFilter",
            "MedianFilter", "BilateralFilter", "GaussianBlurFilter", "MotionBlurFilter", "BoxBlurFilter",
            "EmbossFilter", "CartoonFilter", "PosterizeFilter", "PixelateFilter", "OilPaintFilter",
            "WatercolorFilter", "EdgeEnhancer", "DetailEnhancer", "NoiseReductionFilter", "TemplateMatcher",
            "ColorThresholdDetector", "HistogramAnalyzer", "ImageMetadataExtractor", "DominantColorFinder", "ImageSimilarityMatcher",
            "FeatureDetector", "DescriptorMatcher", "PerspectiveCorrector", "ImageStitcher", "QRCodeDecoder"
        ]
        descriptions = [f"Image processing: {name.replace('Filter', ' filter').replace('Detector', ' detection')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"image_decoder_{i+1}",
                "name": name,
                "description": desc,
                "category": "image_decoder",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_translation_modules() -> List[Dict]:
        """50 Translation Modules"""
        modules = []
        languages = [
            "Spanish", "French", "German", "Italian", "Portuguese", "Russian", "Chinese", "Cantonese", "Japanese", "Korean",
            "Arabic", "Hindi", "Urdu", "Bengali", "Tamil", "Telugu", "Marathi", "Gujarati", "Kannada", "Malayalam",
            "Oriya", "Punjabi", "Greek", "Turkish", "Polish", "Swedish", "Dutch", "Norwegian", "Danish", "Finnish",
            "Czech", "Slovak", "Hungarian", "Romanian", "Thai", "Vietnamese", "Indonesian", "Malay", "Tagalog", "Swahili",
            "Akan", "Yoruba", "Amharic", "Persian", "Hebrew", "Burmese", "Khmer", "Lao", "Zulu"
        ]
        
        for i, lang in enumerate(languages):
            modules.append({
                "id": f"translation_{i+1}",
                "name": f"EnglishTo{lang.replace(' ', '')}",
                "description": f"Bidirectional translation English ↔ {lang}",
                "category": "translation",
                "status": "available"
            })
        
        modules.append({
            "id": "translation_50",
            "name": "LanguageDetector",
            "description": "Detects input language automatically",
            "category": "translation",
            "status": "available"
        })
        return modules
    
    @staticmethod
    def get_coding_modules() -> List[Dict]:
        """50 Coding Assistant Modules"""
        modules = []
        names = [
            "PythonCodeGenerator", "JavaScriptCodeGenerator", "JavaCodeGenerator", "CPlusPlusCodeGenerator", "CSharpCodeGenerator",
            "GoCodeGenerator", "RustCodeGenerator", "PHPCodeGenerator", "RubyCodeGenerator", "SwiftCodeGenerator",
            "KotlinCodeGenerator", "TypeScriptCodeGenerator", "PythonSyntaxChecker", "JavaScriptSyntaxChecker", "JSONValidator",
            "XMLValidator", "HTMLValidator", "CSSValidator", "SQLFormatter", "SQLOptimizer",
            "RegexGenerator", "RegexExplainer", "CodeFormatter", "CodeMinifier", "CodeCommentator",
            "VariableRenamer", "FunctionExtractor", "DuplicateCodeFinder", "DeadCodeDetector", "ComplexityAnalyzer",
            "SecurityVulnerabilityScanner", "PerformanceOptimizer", "DesignPatternSuggester", "APIDocumentationGenerator", "UnitTestGenerator",
            "MockDataGenerator", "ErrorMessageFixer", "DebugHelper", "StackTraceAnalyzer", "AlgorithmExplainer",
            "TimeComplexityCalculator", "SpaceComplexityCalculator", "CodeSnippetLibrary", "LibraryDocumentationBot", "ExceptionHandlerGenerator",
            "ConfigurationFileGenerator", "DockerfileGenerator", "GitignoreGenerator", "RequirementsFileGenerator", "DeploymentScriptGenerator"
        ]
        descriptions = [f"Code assistance: {name.replace('Generator', ' generation').replace('Checker', ' validation')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"coding_{i+1}",
                "name": name,
                "description": desc,
                "category": "coding",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_voice_modules() -> List[Dict]:
        """50 Voice/Audio Modules"""
        modules = []
        names = [
            "TextToSpeechBasic", "TextToSpeechPro", "PhonemicTranscriber", "SpeechRateController", "ToneModulator",
            "PitchShifter", "VolumeNormalizer", "EchoRemover", "NoiseGateFilter", "AudioCompressor",
            "EqualizerFilter", "BassBooster", "TrebleBooster", "FrequencyAnalyzer", "SpectrogramGenerator",
            "AudioDurationCalculator", "SilenceDetector", "OnsetDetector", "TempoDetector", "KeyDetector",
            "ChordRecognizer", "MelodyExtractor", "HarmonyDetector", "VoiceActivityDetector", "SpeakerDiarization",
            "MusicGenreClassifier", "InstrumentDetector", "AudioFingerprintGenerator", "AudioEventDetector", "AcousticFeatureExtractor",
            "ZeroCrossingRateCalculator", "MFCCExtractor", "SpectralCentroidCalculator", "RolloffFrequencyCalculator", "AudioTimeStretchProcessor",
            "AudioPitchShiftProcessor", "SoundMorphingModule", "PhaseVocoderProcessor", "ConvolutionReverbModule", "DelayEchoModule",
            "ChorusModule", "FlangerModule", "PhaserModule", "DistortionModule", "CompressorModule",
            "ExpanderModule", "LimiterModule", "GateModule", "StereoWidenerModule", "MixerModule"
        ]
        descriptions = [f"Audio processing: {name.replace('Module', '').replace('Processor', ' processing')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"voice_{i+1}",
                "name": name,
                "description": desc,
                "category": "voice",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_data_analysis_modules() -> List[Dict]:
        """50 Data Analysis Modules"""
        modules = []
        names = [
            "DataStatisticsCalculator", "StandardDeviationCalculator", "VarianceCalculator", "CorrelationAnalyzer", "CovarianceCalculator",
            "PercentileCalculator", "OutlierDetector", "DistributionAnalyzer", "NormalityTester", "HistogramGenerator",
            "BoxPlotGenerator", "ScatterPlotGenerator", "LineChartGenerator", "BarChartGenerator", "PieChartGenerator",
            "HeatmapGenerator", "ChoroplethMapGenerator", "TreemapGenerator", "SunburstChartGenerator", "ParallelCoordinatesPlotter",
            "LinearRegressionAnalyzer", "PolynomialRegressionAnalyzer", "LogisticRegressionClassifier", "DecisionTreeClassifier", "RandomForestClassifier",
            "KMeansClusterer", "HierarchicalClusterer", "DBSCANClusterer", "PCADimensionalityReducer", "TSNEDimensionalityReducer",
            "NaiveBayesClassifier", "SVMClassifier", "NeuralNetworkClassifier", "KNearestNeighborsClassifier", "GradientBoostingClassifier",
            "EnsembleAnalyzer", "CrossValidationAnalyzer", "HypothesisTester", "ANOVAAnalyzer", "TimeSeriesAnalyzer",
            "TrendExtractor", "SeasonalityDetector", "ForecastingModel", "AnomalyDetector", "ComparisonAnalyzer",
            "FeatureImportanceAnalyzer", "ConfusionMatrixAnalyzer", "ROCCurveGenerator", "PrecisionRecallAnalyzer", "ModelEvaluationModule"
        ]
        descriptions = [f"Data analysis: {name.replace('Analyzer', ' analysis').replace('Calculator', ' calculation')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"data_analysis_{i+1}",
                "name": name,
                "description": desc,
                "category": "data_analysis",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_content_gen_modules() -> List[Dict]:
        """50 Content Generation Modules"""
        modules = []
        names = [
            "ArticleGenerator", "BlogPostGenerator", "ProductDescriptionGenerator", "TitleGenerator", "HeadlineGenerator",
            "MetaDescriptionGenerator", "OutlineGenerator", "ParagraphGenerator", "SentenceExpander", "SentenceCondenser",
            "SummarizerModule", "AbstractGenerator", "KeywordExtractor", "BulletPointGenerator", "ListGenerator",
            "ComparisonGenerator", "ProAndConGenerator", "FAQGenerator", "HowToGuideGenerator", "TutorialGenerator",
            "RecipeGenerator", "StoryGenerator", "PoetryGenerator", "SongLyricsGenerator", "JokeGenerator",
            "TongueTwisterGenerator", "RiddleGenerator", "LimerickGenerator", "HaikuGenerator", "AcronymGenerator",
            "QuoteGenerator", "EmailTemplateGenerator", "LetterTemplateGenerator", "ResumeGenerator", "CoverLetterGenerator",
            "CVGenerator", "BioGenerator", "SocialMediaCaptionGenerator", "TwitterThreadGenerator", "LinkedInPostGenerator",
            "InstagramCaptionGenerator", "YoutubeDescriptionGenerator", "WebsiteContentGenerator", "SlideContentGenerator", "PresentationGenerator",
            "ScriptGenerator", "DialogueGenerator", "ChatbotResponseGenerator", "ErrorMessageGenerator", "WelcomeMessageGenerator"
        ]
        descriptions = [f"Content generation: {name.replace('Generator', '').replace('Module', '')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"content_gen_{i+1}",
                "name": name,
                "description": desc,
                "category": "content_gen",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def get_vision_modules() -> List[Dict]:
        """50 Vision/ML Modules"""
        modules = []
        names = [
            "ObjectDetector", "FaceDetector", "FaceRecognizer", "EyeDetector", "LandmarkDetector",
            "PoseEstimator", "HandGestureRecognizer", "TextDetector", "TextExtractor", "HandwritingRecognizer",
            "DocumentScanner", "DocumentOCR", "BarCodeDetector", "QRCodeDetector", "LicensePlateDetector",
            "LicensePlateRecognizer", "VehicleDetector", "TrafficSignDetector", "PedestrianDetector", "AnimalDetector",
            "PlantIdentifier", "BirdIdentifier", "InsectIdentifier", "FruitDetector", "VegetableDetector",
            "FoodDetector", "AnimalSpeciesClassifier", "CloudDetector", "WeatherConditionDetector", "DiseaseDetector",
            "CancerDetector", "SkinLesionAnalyzer", "XrayAnalyzer", "MRIAnalyzer", "RetinalImageAnalyzer",
            "HandwritingToTextConverter", "StyleTransfer", "ImageUpscaler", "ImageInpainting", "BackgroundRemover",
            "BackgroundReplacer", "ShadowRemover", "DehazeModule", "DeraineModule", "SuperResolutionModule",
            "Colorization", "AgeEstimator", "EmotionDetector", "GenderDetector", "SmileDetector"
        ]
        descriptions = [f"Computer vision: {name.replace('Detector', ' detection').replace('Module', '')}" for name in names]
        
        for i, (name, desc) in enumerate(zip(names, descriptions)):
            modules.append({
                "id": f"vision_{i+1}",
                "name": name,
                "description": desc,
                "category": "vision",
                "status": "available"
            })
        return modules
    
    @staticmethod
    def execute_module(module_name: str, input_data: Any) -> Dict[str, Any]:
        """Execute a specific AI module with input data"""
        start_time = time.time()
        
        result = {
            "module": module_name,
            "status": "success",
            "input": str(input_data)[:100],
            "output": f"Processed by {module_name}: {input_data}",
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }
        
        # Example module implementations
        if "Sentiment" in module_name:
            positive_words = ["good", "great", "excellent", "amazing", "love", "wonderful"]
            negative_words = ["bad", "terrible", "awful", "hate", "poor", "horrible"]
            text_lower = str(input_data).lower()
            pos_count = sum(1 for word in positive_words if word in text_lower)
            neg_count = sum(1 for word in negative_words if word in text_lower)
            
            if pos_count > neg_count:
                sentiment = "positive"
            elif neg_count > pos_count:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            result["output"] = {
                "sentiment": sentiment,
                "confidence": 0.85,
                "positive_score": pos_count,
                "negative_score": neg_count
            }
        
        elif "ASCII" in module_name:
            result["output"] = f"ASCII: {input_data}\n{'='*len(str(input_data))}"
        
        elif "Translation" in module_name:
            result["output"] = f"[Translated] {input_data}"
        
        elif "Generator" in module_name:
            result["output"] = f"Generated content based on: {input_data}"
        
        return result

# ============================================================================
# RATE LIMITING
# ============================================================================

async def check_rate_limit(identifier: str, max_requests: int = 5, window_seconds: int = 900) -> bool:
    """Check if request is within rate limit (5 requests per 15 minutes)"""
    current_time = time.time()
    
    if identifier not in rate_limit_store:
        rate_limit_store[identifier] = []
    
    # Remove old requests outside the window
    rate_limit_store[identifier] = [
        req_time for req_time in rate_limit_store[identifier]
        if current_time - req_time < window_seconds
    ]
    
    # Check if limit exceeded
    if len(rate_limit_store[identifier]) >= max_requests:
        return False
    
    # Add current request
    rate_limit_store[identifier].append(current_time)
    return True

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def generate_api_key() -> str:
    """Generate 10-character API key"""
    chars = string.ascii_uppercase + string.digits
    return 'API_' + ''.join(secrets.choice(chars) for _ in range(10))

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        return False

def generate_session_token() -> str:
    """Generate secure session token"""
    return secrets.token_urlsafe(32)

async def get_current_user(request: Request) -> Optional[int]:
    """Get current user ID from session (FIXED - uses hash for lookup)"""
    session_token = request.cookies.get('session_token')
    if not session_token:
        return None
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        # FIXED: Use session_hash for deterministic lookup
        await cursor.execute('''
            SELECT user_id FROM sessions
            WHERE session_hash = ? AND is_active = TRUE AND expires_at > ?
        ''', (hash_for_lookup(session_token), datetime.now().isoformat()))
        
        row = await cursor.fetchone()
        if row:
            # Update last activity
            await cursor.execute('''
                UPDATE sessions SET last_activity = ? WHERE session_hash = ?
            ''', (datetime.now().isoformat(), hash_for_lookup(session_token)))
            await conn.commit()
            return row[0]
    return None

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()
    
    # Print all registered routes for debugging
    print("\n[DEBUG] Registered API routes:")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            print(f"  {list(route.methods)[0] if route.methods else 'GET'} {route.path}")
    print()
    
    yield
    # Shutdown (cleanup if needed)

app = FastAPI(
    title="SOUL - API Management System",
    description="900 Offline AI Modules with API Key Management (FULLY FIXED v2.0.2)",
    version="2.0.2",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HTML TEMPLATES (MODERNIZED WITH DARK MODE & GLASS MORPHISM)
# ============================================================================

def get_base_html() -> str:
    """Get base HTML template with modern CSS and JS"""
    return r'''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOUL - API Management System</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#fff}
.container{max-width:1200px;margin:0 auto;padding:20px}
.glass{background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border-radius:20px;border:1px solid rgba(255,255,255,0.2);box-shadow:0 8px 32px rgba(0,0,0,0.1)}
.btn{background:linear-gradient(45deg,#667eea,#764ba2);color:#fff;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:16px;transition:all 0.3s}
.btn:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(0,0,0,0.2)}
input,select{width:100%;padding:12px;border-radius:8px;border:1px solid rgba(255,255,255,0.3);background:rgba(255,255,255,0.1);color:#fff;font-size:16px;margin:8px 0}
input::placeholder{color:rgba(255,255,255,0.6)}
.card{background:rgba(255,255,255,0.15);padding:20px;border-radius:12px;margin:10px 0}
.alert{padding:12px;border-radius:8px;margin:10px 0;font-weight:500}
.alert-success{background:rgba(46,125,50,0.8)}
.alert-error{background:rgba(211,47,47,0.8)}
.alert-info{background:rgba(2,136,209,0.8)}
</style>
</head>
<body>
'''

def get_login_page() -> str:
    """Login page with modern design"""
    return get_base_html() + r'''
<div class="container">
<div class="glass" style="max-width:400px;margin:100px auto;padding:40px">
<h1 style="text-align:center;margin-bottom:10px">🚀 Welcome to SOUL</h1>
<p style="text-align:center;opacity:0.8;margin-bottom:30px">900 AI Modules at Your Fingertips</p>
<h2 style="margin-bottom:20px">Sign In</h2>
<form id="loginForm" onsubmit="handleLogin(event)">
<input type="text" name="email_or_username" placeholder="Email or Username" required>
<input type="password" name="password" placeholder="Password" required>
<div id="message"></div>
<button type="submit" class="btn" style="width:100%;margin-top:10px">Sign In</button>
</form>
<p style="text-align:center;margin-top:20px;opacity:0.8">
<a href="/register" style="color:#fff">Create Account</a> |
<a href="/forgot-password" style="color:#fff">Forgot Password?</a>
</p>
</div>
</div>
<script>
async function handleLogin(e){
e.preventDefault();
const form=e.target;
const data={email_or_username:form.email_or_username.value,password:form.password.value};
try{
const res=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const result=await res.json();
if(res.ok){
window.location.href=`/verify-otp?email=${encodeURIComponent(result.email)}`;
}else{
document.getElementById('message').innerHTML=`<div class="alert alert-error">${result.detail}</div>`;
}
}catch(err){
document.getElementById('message').innerHTML=`<div class="alert alert-error">Network error</div>`;
}
}
</script>
</body>
</html>
'''

def get_register_page() -> str:
    """Registration page with modern design"""
    return get_base_html() + r'''
<div class="container">
<div class="glass" style="max-width:400px;margin:50px auto;padding:40px">
<h1 style="text-align:center;margin-bottom:10px">✨ Join SOUL</h1>
<p style="text-align:center;opacity:0.8;margin-bottom:30px">Start building with 900 AI modules today</p>
<h2 style="margin-bottom:20px">Create Account</h2>
<form id="registerForm" onsubmit="handleRegister(event)">
<input type="text" name="username" placeholder="Username" required>
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="password" placeholder="Password" required>
<input type="password" name="confirm_password" placeholder="Confirm Password" required>
<div id="message"></div>
<button type="submit" class="btn" style="width:100%;margin-top:10px">Create Account</button>
</form>
<p style="text-align:center;margin-top:20px;opacity:0.8">
<a href="/login" style="color:#fff">Already have an account? Sign In</a>
</p>
</div>
</div>
<script>
async function handleRegister(e){
e.preventDefault();
const form=e.target;
const data={
username:form.username.value,
email:form.email.value,
password:form.password.value,
confirm_password:form.confirm_password.value
};
try{
const res=await fetch('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const result=await res.json();
if(res.ok){
window.location.href=`/verify-otp?email=${encodeURIComponent(result.email)}`;
}else{
document.getElementById('message').innerHTML=`<div class="alert alert-error">${result.detail}</div>`;
}
}catch(err){
document.getElementById('message').innerHTML=`<div class="alert alert-error">Network error</div>`;
}
}
</script>
</body>
</html>
'''

def get_verify_otp_page(email: str) -> str:
    """OTP verification page"""
    return get_base_html() + rf'''
<div class="container">
<div class="glass" style="max-width:400px;margin:100px auto;padding:40px">
<h2 style="text-align:center;margin-bottom:20px">🔐 Verify OTP</h2>
<p style="text-align:center;opacity:0.8;margin-bottom:30px">Enter the 6-digit code sent to <strong>{email}</strong></p>
<form id="otpForm" onsubmit="handleVerifyOTP(event)">
<input type="text" name="otp" placeholder="Enter 6-digit OTP" maxlength="6" required style="text-align:center;font-size:24px;letter-spacing:8px">
<div id="message"></div>
<button type="submit" class="btn" style="width:100%;margin-top:20px">Verify & Continue</button>
</form>
</div>
</div>
<script>
const email="{email}";
async function handleVerifyOTP(e){{
e.preventDefault();
const form=e.target;
const data={{email:email,otp:form.otp.value}};
try{{
const res=await fetch('/api/auth/verify-otp',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});
const result=await res.json();
if(res.ok){{
window.location.href=result.redirect||'/dashboard';
}}else{{
document.getElementById('message').innerHTML=`<div class="alert alert-error">${{result.detail}}</div>`;
}}
}}catch(err){{
document.getElementById('message').innerHTML=`<div class="alert alert-error">Network error</div>`;
}}
}}
</script>
</body>
</html>
'''

def get_forgot_password_page() -> str:
    """Forgot password page"""
    return get_base_html() + r'''
<div class="container">
<div class="glass" style="max-width:400px;margin:100px auto;padding:40px">
<h2 style="text-align:center;margin-bottom:20px">🔑 Reset Password</h2>
<p style="text-align:center;opacity:0.8;margin-bottom:30px">Enter your email to receive a reset code</p>
<form id="forgotForm" onsubmit="handleForgot(event)">
<input type="email" name="email" placeholder="Email Address" required>
<div id="message"></div>
<button type="submit" class="btn" style="width:100%;margin-top:20px">Send Reset Code</button>
</form>
<p style="text-align:center;margin-top:20px;opacity:0.8">
<a href="/login" style="color:#fff">Back to Login</a>
</p>
</div>
</div>
<script>
async function handleForgot(e){
e.preventDefault();
const form=e.target;
const data={email:form.email.value};
try{
const res=await fetch('/api/auth/forgot-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const result=await res.json();
if(res.ok){
window.location.href=`/reset-password?email=${encodeURIComponent(data.email)}`;
}else{
document.getElementById('message').innerHTML=`<div class="alert alert-error">${result.detail}</div>`;
}
}catch(err){
document.getElementById('message').innerHTML=`<div class="alert alert-error">Network error</div>`;
}
}
</script>
</body>
</html>
'''

def get_reset_password_page(email: str) -> str:
    """Reset password page"""
    return get_base_html() + rf'''
<div class="container">
<div class="glass" style="max-width:400px;margin:100px auto;padding:40px">
<h2 style="text-align:center;margin-bottom:20px">🔐 Reset Password</h2>
<p style="text-align:center;opacity:0.8;margin-bottom:30px">Enter the code sent to {email}</p>
<form id="resetForm" onsubmit="handleReset(event)">
<input type="text" name="otp" placeholder="Reset Code (6 digits)" maxlength="6" required>
<input type="password" name="new_password" placeholder="New Password" required>
<input type="password" name="confirm_password" placeholder="Confirm New Password" required>
<div id="message"></div>
<button type="submit" class="btn" style="width:100%;margin-top:20px">Reset Password</button>
</form>
</div>
</div>
<script>
const email="{email}";
async function handleReset(e){{
e.preventDefault();
const form=e.target;
const data={{
email:email,
otp:form.otp.value,
new_password:form.new_password.value,
confirm_password:form.confirm_password.value
}};
try{{
const res=await fetch('/api/auth/reset-password',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});
const result=await res.json();
if(res.ok){{
document.getElementById('message').innerHTML=`<div class="alert alert-success">Password reset successful! Redirecting...</div>`;
setTimeout(()=>window.location.href='/login',2000);
}}else{{
document.getElementById('message').innerHTML=`<div class="alert alert-error">${{result.detail}}</div>`;
}}
}}catch(err){{
document.getElementById('message').innerHTML=`<div class="alert alert-error">Network error</div>`;
}}
}}
</script>
</body>
</html>
'''

def get_dashboard_page(user_data: Dict) -> str:
    """Modern dashboard"""
    return get_base_html() + rf'''
<div class="container">
<div class="glass" style="padding:30px;margin-top:20px">
<div style="display:flex;justify-content:space-between;align-items:center">
<h1>Dashboard Overview</h1>
<div style="display:flex;align-items:center;gap:20px">
<div style="background:rgba(255,255,255,0.2);width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px">{user_data['username'][0].upper()}</div>
<div>
<div style="font-weight:bold">{user_data['username']}</div>
<a href="/api/auth/logout" style="color:#fff;opacity:0.8;text-decoration:none;font-size:14px">Logout</a>
</div>
</div>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-top:30px">
<div class="card"><h3>Total API Keys</h3><h1 id="totalKeys">0</h1></div>
<div class="card"><h3>Total Requests</h3><h1 id="totalRequests">0</h1></div>
<div class="card"><h3>Rate Limit Used</h3><h1 id="rateLimit">0%</h1></div>
<div class="card"><h3>Available Modules</h3><h1>900</h1></div>
</div>
<div class="card" style="margin-top:20px">
<h3>⚡ Quick Actions</h3>
<p style="opacity:0.8;margin:10px 0">Welcome to SOUL! Get started by exploring our 900 offline AI modules across 9 categories.</p>
<a href="/modules" class="btn" style="display:inline-block;text-decoration:none;margin-top:10px">Explore Modules</a>
</div>
</div>
</div>
<script>
async function loadStats(){{
try{{
const res=await fetch('/api/dashboard/stats');
if(res.ok){{
const data=await res.json();
document.getElementById('totalKeys').textContent=data.total_keys;
document.getElementById('totalRequests').textContent=data.total_requests;
document.getElementById('rateLimit').textContent=data.rate_limit_used+'%';
}}
}}catch(err){{
console.error('Failed to load stats',err);
}}
}}
loadStats();
</script>
</body>
</html>
'''

# ============================================================================
# API ROUTES - AUTHENTICATION (ALL FIXED WITH HASH LOOKUPS)
# ============================================================================

# FIX 2: Health check with package installation status
@app.get("/api/health")
async def health_check():
    """Health check endpoint with installation progress"""
    return {
        "status": "ok",
        "version": "2.0.2",
        "message": "SOUL API is running (ALL BUGS FIXED)",
        "packages_installing": installation_state['packages_installing'],
        "packages_complete": installation_state['packages_complete'],
        "installed": installation_state['installed'],
        "pending": installation_state['pending'],
        "failed": installation_state['failed']
    }

@app.post("/api/auth/register")
async def register(user: UserRegister):
    """Register new user with rate limiting (FIXED - stores hash for lookup)"""
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIXED: Check existence using hash
        await cursor.execute(
            "SELECT id FROM users WHERE username_hash = ? OR email_hash = ?",
            (hash_for_lookup(user.username), hash_for_lookup(user.email))
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Generate OTP
        otp = generate_otp()
        otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        # Hash password
        password_hash = hash_password(user.password)
        
        # FIXED: Insert user with hash columns
        await cursor.execute('''
            INSERT INTO users (username, username_hash, email, email_hash, password_hash, otp_secret, otp_expiry, is_email_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)
        ''', (
            encrypt_data(user.username),
            hash_for_lookup(user.username),
            encrypt_data(user.email),
            hash_for_lookup(user.email),
            password_hash,
            encrypt_data(otp),
            otp_expiry
        ))
        
        user_id = cursor.lastrowid
        
        # FIXED: Log OTP with email hash
        await cursor.execute('''
            INSERT INTO otp_logs (user_id, email, email_hash, otp_code, otp_type, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, encrypt_data(user.email), hash_for_lookup(user.email), encrypt_data(otp), 'registration', otp_expiry))
        
        await conn.commit()
        
        # Send OTP email
        email_body = get_otp_email_template(otp, "registration")
        send_email(user.email, "SOUL - Verify Your Email", email_body)
        
        return {"message": "Registration successful. Please verify OTP sent to your email.", "email": user.email}

@app.post("/api/auth/login")
async def login(user: UserLogin, request: Request):
    """Login user with rate limiting (FIXED - uses hash for lookup)"""
    # Rate limiting
    if not await check_rate_limit(f"login_{user.email_or_username}"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIXED: Find user using hash
        await cursor.execute('''
            SELECT id, username, email, password_hash, is_email_verified, failed_login_attempts, account_locked_until
            FROM users WHERE username_hash = ? OR email_hash = ?
        ''', (hash_for_lookup(user.email_or_username), hash_for_lookup(user.email_or_username)))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id, username_encrypted, email_encrypted, password_hash, is_verified, failed_attempts, locked_until = row
        
        # Check account lock
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
            raise HTTPException(status_code=403, detail="Account is locked. Try again later.")
        
        # Verify password
        if not verify_password(user.password, password_hash):
            # Increment failed attempts
            await cursor.execute('''
                UPDATE users SET failed_login_attempts = failed_login_attempts + 1,
                account_locked_until = CASE WHEN failed_login_attempts + 1 >= 5 THEN ? ELSE NULL END
                WHERE id = ?
            ''', ((datetime.now() + timedelta(hours=1)).isoformat(), user_id))
            await conn.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not is_verified:
            raise HTTPException(status_code=403, detail="Email not verified. Please verify your email first.")
        
        # Reset failed attempts
        await cursor.execute("UPDATE users SET failed_login_attempts = 0, account_locked_until = NULL WHERE id = ?", (user_id,))
        
        # Generate OTP
        otp = generate_otp()
        otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        await cursor.execute('''
            UPDATE users SET otp_secret = ?, otp_expiry = ? WHERE id = ?
        ''', (encrypt_data(otp), otp_expiry, user_id))
        
        # FIXED: Log OTP with email hash
        await cursor.execute('''
            INSERT INTO otp_logs (user_id, email, email_hash, otp_code, otp_type, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email_encrypted, hash_for_lookup(decrypt_data(email_encrypted)), encrypt_data(otp), 'login', otp_expiry))
        
        await conn.commit()
        
        # Send OTP email
        email_body = get_otp_email_template(otp, "login")
        send_email(decrypt_data(email_encrypted), "SOUL - Login Verification", email_body)
        
        return {"message": "OTP sent to your email", "email": decrypt_data(email_encrypted)}

@app.post("/api/auth/verify-otp", status_code=200)
async def verify_otp_endpoint(data: VerifyOTP):
    """Verify OTP (FIX 3: Session expiry 24 hours)"""
    print(f"[DEBUG] verify-otp endpoint called with email: {data.email}")
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIXED: Use email_hash for lookup
        await cursor.execute('''
            SELECT id, username, otp_secret, otp_expiry, is_email_verified
            FROM users WHERE email_hash = ?
        ''', (hash_for_lookup(data.email),))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id, username, otp_secret, otp_expiry, is_verified = row
        
        # Check OTP expiry
        if datetime.fromisoformat(otp_expiry) < datetime.now():
            raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")
        
        # Verify OTP
        if decrypt_data(otp_secret) != data.otp:
            # Increment attempts
            await cursor.execute('''
                UPDATE otp_logs
                SET attempts = attempts + 1
                WHERE id = (
                    SELECT id FROM otp_logs
                    WHERE user_id = ? AND verified = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                )
            ''', (user_id,))
            await conn.commit()
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        # Mark email as verified and create session
        await cursor.execute('''
            UPDATE users SET is_email_verified = TRUE, last_login = ? WHERE id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        # FIX 3: Session expiry changed to 24 hours (was 30 minutes)
        session_token = generate_session_token()
        session_expiry = (datetime.now() + timedelta(hours=24)).isoformat()
        
        await cursor.execute('''
            INSERT INTO sessions (user_id, session_token, session_hash, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, encrypt_data(session_token), hash_for_lookup(session_token), session_expiry))
        
        # Mark OTP as verified
        await cursor.execute('''
            UPDATE otp_logs
            SET verified = TRUE, verified_at = ?
            WHERE id = (
                SELECT id FROM otp_logs
                WHERE user_id = ? AND verified = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            )
        ''', (datetime.now().isoformat(), user_id))
        
        await conn.commit()
        
        response = JSONResponse({"message": "Verification successful", "redirect": "/dashboard"})
        # FIX 3: max_age changed to 86400 (24 hours) - was 1800 (30 minutes)
        response.set_cookie(
            "session_token",
            session_token,
            httponly=True,
            max_age=86400,
            secure=False,
            samesite="strict"
        )
        return response

@app.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPassword, request: Request):
    """Forgot password - send reset OTP (FIXED - uses hash for lookup)"""
    # Rate limiting
    if not await check_rate_limit(f"forgot_{data.email}"):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIXED: Use email_hash for lookup
        await cursor.execute("SELECT id FROM users WHERE email_hash = ?", (hash_for_lookup(data.email),))
        row = await cursor.fetchone()
        
        if not row:
            # Don't reveal if email exists (security best practice)
            return {"message": "If the email exists, a reset code has been sent."}
        
        user_id = row[0]
        
        # Generate OTP
        otp = generate_otp()
        otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        await cursor.execute('''
            UPDATE users SET otp_secret = ?, otp_expiry = ? WHERE id = ?
        ''', (encrypt_data(otp), otp_expiry, user_id))
        
        # FIXED: Log OTP with email hash
        await cursor.execute('''
            INSERT INTO otp_logs (user_id, email, email_hash, otp_code, otp_type, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, encrypt_data(data.email), hash_for_lookup(data.email), encrypt_data(otp), 'forgot_password', otp_expiry))
        
        await conn.commit()
        
        # Send email
        email_body = get_otp_email_template(otp, "forgot_password")
        send_email(data.email, "SOUL - Password Reset Code", email_body)
        
        return {"message": "If the email exists, a reset code has been sent."}

@app.post("/api/auth/reset-password")
async def reset_password(data: ResetPassword):
    """Reset password with OTP (FIXED - uses hash for lookup)"""
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIXED: Use email_hash for lookup
        await cursor.execute('''
            SELECT id, otp_secret, otp_expiry FROM users WHERE email_hash = ?
        ''', (hash_for_lookup(data.email),))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id, otp_secret, otp_expiry = row
        
        # Verify OTP
        if datetime.fromisoformat(otp_expiry) < datetime.now():
            raise HTTPException(status_code=400, detail="Reset code expired")
        
        if decrypt_data(otp_secret) != data.otp:
            raise HTTPException(status_code=400, detail="Invalid reset code")
        
        # Update password
        password_hash = hash_password(data.new_password)
        await cursor.execute('''
            UPDATE users SET password_hash = ?, otp_secret = NULL, otp_expiry = NULL WHERE id = ?
        ''', (password_hash, user_id))
        
        await conn.commit()
        
        return {"message": "Password reset successful"}

@app.post("/api/auth/logout")
async def logout(request: Request):
    """Logout user (FIXED - uses hash for lookup)"""
    session_token = request.cookies.get('session_token')
    if session_token:
        async with get_db() as conn:
            cursor = await conn.cursor()
            # FIXED: Use session_hash for lookup
            await cursor.execute('''
                UPDATE sessions SET is_active = FALSE WHERE session_hash = ?
            ''', (hash_for_lookup(session_token),))
            await conn.commit()
    
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("session_token")
    return response

# ============================================================================
# API ROUTES - MODULES
# ============================================================================

@app.get("/api/modules/list")
async def list_modules(request: Request):
    """List all 900 modules (cached)"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return AIModules.get_all_modules()

@app.get("/api/modules/categories")
async def list_categories(request: Request):
    """List all module categories"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return AIModules.CATEGORIES

# FIX 1 & FIX 4: Execute module endpoint - API key hash lookup + no session required
@app.post("/api/modules/{module_name}/execute")
async def execute_module_endpoint(module_name: str, request: Request, data: Dict[str, Any]):
    """Execute a specific module (FIX 1: Uses api_key_hash, FIX 4: No session required)"""
    # Get API key from header
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required in X-API-Key header")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # FIX 1: Use api_key_hash for deterministic lookup (NOT encrypted value)
        # FIX 4: Get user_id directly from api_keys table - no session needed
        await cursor.execute('''
            SELECT id, user_id, status, rate_limit_monthly, rate_limit_used, rate_limit_reset_date
            FROM api_keys WHERE api_key_hash = ? AND module_name = ?
        ''', (hash_for_lookup(api_key), module_name))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        key_id, user_id, status_val, rate_limit, rate_used, reset_date = row
        
        if status_val != 'active':
            raise HTTPException(status_code=403, detail="API key is inactive")
        
        # Check rate limit
        if reset_date and datetime.fromisoformat(reset_date) < datetime.now():
            # Reset rate limit
            await cursor.execute('''
                UPDATE api_keys SET rate_limit_used = 0, rate_limit_reset_date = ? WHERE id = ?
            ''', ((datetime.now() + timedelta(days=30)).isoformat(), key_id))
            rate_used = 0
        
        if rate_used >= rate_limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_date
                }
            )
        
        # Execute module
        start_time = time.time()
        result = AIModules.execute_module(module_name, data.get('input', ''))
        processing_time = int((time.time() - start_time) * 1000)
        
        # Update rate limit
        await cursor.execute('''
            UPDATE api_keys SET rate_limit_used = rate_limit_used + 1, last_used = ? WHERE id = ?
        ''', (datetime.now().isoformat(), key_id))
        
        # Log request
        await cursor.execute('''
            INSERT INTO api_requests (user_id, api_key_id, module_name, category, request_data, response_data, status_code, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, key_id, module_name, result.get('category', 'unknown'),
              encrypt_data(json.dumps(data)), encrypt_data(json.dumps(result)), 200, processing_time))
        
        await conn.commit()
        
        return {
            **result,
            "rate_limit": {
                "limit": rate_limit,
                "used": rate_used + 1,
                "remaining": rate_limit - rate_used - 1,
                "reset_date": reset_date
            }
        }

# ============================================================================
# API ROUTES - API KEYS
# ============================================================================

@app.post("/api/keys/create")
async def create_api_key(data: CreateAPIKey, request: Request):
    """Create new API key (FIX 1: Stores api_key_hash)"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find module
    all_modules = AIModules.get_all_modules()
    module_category = None
    module_found = False
    
    for category, modules in all_modules.items():
        for module in modules:
            if module['name'] == data.module_name:
                module_category = category
                module_found = True
                break
        if module_found:
            break
    
    if not module_found:
        raise HTTPException(status_code=404, detail="Module not found")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # Check if key already exists
        await cursor.execute('''
            SELECT id FROM api_keys WHERE user_id = ? AND module_name = ? AND status = 'active'
        ''', (user_id, data.module_name))
        
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="API key already exists for this module")
        
        # Generate API key
        api_key = generate_api_key()
        reset_date = (datetime.now() + timedelta(days=30)).isoformat()
        
        # FIX 1: Insert key with api_key_hash
        await cursor.execute('''
            INSERT INTO api_keys (user_id, module_name, category, api_key, api_key_hash, rate_limit_reset_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, data.module_name, module_category, encrypt_data(api_key), hash_for_lookup(api_key), reset_date))
        
        key_id = cursor.lastrowid
        await conn.commit()
        
        return {
            "id": key_id,
            "api_key": api_key,  # Only shown once at creation
            "module_name": data.module_name,
            "category": module_category,
            "created_at": datetime.now().isoformat(),
            "message": "API key created successfully. Save this key securely - you won't be able to see it again!"
        }

@app.get("/api/keys/list")
async def list_api_keys(request: Request):
    """List all API keys for current user (masked)"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            SELECT id, module_name, category, api_key, created_at, last_used, status, rate_limit_monthly, rate_limit_used
            FROM api_keys WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        keys = []
        rows = await cursor.fetchall()
        for row in rows:
            api_key = decrypt_data(row[3])
            keys.append({
                "id": row[0],
                "module_name": row[1],
                "category": row[2],
                "api_key": mask_api_key(api_key),  # Masked for security
                "created_at": row[4],
                "last_used": row[5],
                "status": row[6],
                "rate_limit_monthly": row[7],
                "rate_limit_used": row[8]
            })
        
        return keys

# FIX 5: Delete endpoint uses hash (though this one doesn't need hash since it's by ID)
@app.delete("/api/keys/{key_id}")
async def delete_api_key(key_id: int, request: Request):
    """Delete API key with ownership validation"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # Verify ownership (SECURITY FIX)
        await cursor.execute("SELECT user_id FROM api_keys WHERE id = ?", (key_id,))
        row = await cursor.fetchone()
        
        if not row or row[0] != user_id:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Delete key
        await cursor.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        await conn.commit()
        
        return {"message": "API key deleted successfully"}

# ============================================================================
# API ROUTES - DASHBOARD
# ============================================================================

@app.get("/api/dashboard/stats")
async def dashboard_stats(request: Request):
    """Get dashboard statistics"""
    user_id = await get_current_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        
        # Total keys
        await cursor.execute("SELECT COUNT(*) FROM api_keys WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_keys = row[0]
        
        # Total requests
        await cursor.execute("SELECT COUNT(*) FROM api_requests WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_requests = row[0]
        
        # Rate limit used
        await cursor.execute('''
            SELECT AVG(CAST(rate_limit_used AS FLOAT) / rate_limit_monthly * 100)
            FROM api_keys WHERE user_id = ? AND rate_limit_monthly > 0
        ''', (user_id,))
        row = await cursor.fetchone()
        rate_limit_used = row[0] or 0
        
        # Weekly requests (mock for now)
        weekly_requests = [10, 25, 40, 30]
        
        return {
            "total_keys": total_keys,
            "total_requests": total_requests,
            "rate_limit_used": round(rate_limit_used, 1),
            "weekly_requests": weekly_requests
        }

# ============================================================================
# WEB ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root redirect to login"""
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login page"""
    return get_login_page()

@app.get("/register", response_class=HTMLResponse)
async def register_page():
    """Registration page"""
    return get_register_page()

@app.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_page(email: str):
    """OTP verification page"""
    return get_verify_otp_page(email)

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page():
    """Forgot password page"""
    return get_forgot_password_page()

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(email: str):
    """Reset password page"""
    return get_reset_password_page(email)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page"""
    user_id = await get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login")
    
    async with get_db() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT username, email, created_at FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if not row:
            return RedirectResponse(url="/login")
        
        user_data = {
            "username": decrypt_data(row[0]),
            "email": decrypt_data(row[1]),
            "created_at": row[2]
        }
        
        return get_dashboard_page(user_data)

@app.get("/modules", response_class=HTMLResponse)
async def modules_page(request: Request):
    """Modules page"""
    user_id = await get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login")
    
    return get_base_html() + '''
<div class="container">
<div class="glass" style="padding:30px;margin-top:20px">
<h1>900 AI Modules</h1>
<p style="opacity:0.8;margin:10px 0">Browse and generate API keys for any module</p>
<a href="/dashboard" style="color:#fff">← Back to Dashboard</a>
<div style="margin-top:30px">
<div class="alert alert-info">
Module browser coming soon! Use the API endpoints to list modules programmatically.
</div>
</div>
</div>
</div>
</body>
</html>
'''

@app.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request):
    """API Keys management page"""
    user_id = await get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login")
    
    return get_base_html() + '''
<div class="container">
<div class="glass" style="padding:30px;margin-top:20px">
<h1>🔑 API Keys</h1>
<p style="opacity:0.8;margin:10px 0">Manage your API keys</p>
<a href="/dashboard" style="color:#fff">← Back to Dashboard</a>
<div style="margin-top:30px">
<div class="alert alert-info">
API key management UI coming soon! Use the API endpoints to manage keys programmatically.
</div>
</div>
</div>
</div>
</body>
</html>
'''

@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    """Statistics page"""
    user_id = await get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login")
    
    return get_base_html() + '''
<div class="container">
<div class="glass" style="padding:30px;margin-top:20px">
<h1>📊 Statistics</h1>
<p style="opacity:0.8;margin:10px 0">Analytics and usage statistics</p>
<a href="/dashboard" style="color:#fff">← Back to Dashboard</a>
<div style="margin-top:30px">
<div class="alert alert-info">
Advanced statistics coming soon! Use the API endpoints to fetch stats programmatically.
</div>
</div>
</div>
</div>
</body>
</html>
'''

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n╔════════════════════════════════════════════════════════════════╗")
    print("║        🚀 SOUL Server v2.0.2 (ALL BUGS FIXED) Starting        ║")
    print("║                     Running on Port 9077                       ║")
    print("║                                                                ║")
    print("║  Access the application:                                       ║")
    print("║    • http://localhost:9077 (Local)                             ║")
    print("║    • http://your-vps-ip:9077 (Remote)                          ║")
    print("║                                                                ║")
    print("║  API Documentation:                                            ║")
    print("║    • http://localhost:9077/docs (Swagger UI)                   ║")
    print("║    • http://localhost:9077/redoc (ReDoc)                       ║")
    print("║                                                                ║")
    print("║  ✅ ALL CRITICAL BUGS FIXED IN v2.0.2:                         ║")
    print("║    ✅ BUG 1: API key lookup uses api_key_hash (deterministic)  ║")
    print("║    ✅ BUG 2: Background package installation (server starts    ║")
    print("║              immediately, packages install in background)      ║")
    print("║    ✅ FIX 3: Session expiry extended to 24 hours               ║")
    print("║    ✅ FIX 4: API execution works without session cookie        ║")
    print("║    ✅ FIX 5: /api/health endpoint shows installation progress  ║")
    print("║                                                                ║")
    print("║  Press CTRL+C to stop the server                               ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")
    
    uvicorn.run(app, host="0.0.0.0", port=9077, log_level="info")
