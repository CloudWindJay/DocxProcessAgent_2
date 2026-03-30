@echo off
echo ===================================================
echo      Starting DocxProcessAgent
echo ===================================================
echo.

echo [1/2] Starting FastAPI Backend on Port 8000...
start "Docx Agent - Backend (FastAPI)" cmd /c "conda run -p E:\Agent\env\qwen python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Starting React Frontend on Port 5173...
cd frontend
start "Docx Agent - Frontend (Vite)" cmd /c "conda run -p E:\Agent\env\qwen npm run dev"
cd ..

echo.
echo ===================================================
echo ✅ Services are starting in new windows!
echo 🌐 Frontend URL: http://localhost:5173
echo 🔌 Backend URL: http://localhost:8000/docs
echo ===================================================
echo.
echo To STOP the application, simply close the two new command prompt windows that just opened.
echo.
pause
