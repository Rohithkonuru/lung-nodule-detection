@echo off
echo 🫁 LungAI Frontend Setup
echo ========================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is not installed. Please install Node.js 16+ first.
    pause
    exit /b 1
)

echo ✓ Node.js version: 
node --version
echo ✓ npm version:
npm --version
echo.

REM Install dependencies
echo 📦 Installing dependencies...
call npm install

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✓ Dependencies installed
echo.

REM Create .env if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file...
    copy .env.example .env
    echo ✓ .env file created (please update with your API URL)
) else (
    echo ✓ .env file already exists
)

echo.
echo 🚀 Setup complete!
echo.
echo Next steps:
echo 1. Update .env with your Flask API URL
echo 2. Run: npm start
echo 3. Open http://localhost:3000
echo.
pause
