@echo off
REM Create root directory
mkdir pims_reconciliation
cd pims_reconciliation

REM Create main files
type nul > app.py
type nul > requirements.txt

REM Create data directories and files
mkdir data
mkdir data\itam
mkdir data\active_services

type nul > data\itam\itam_dump.csv
type nul > data\active_services\active_services.csv

REM Create templates directory and files
mkdir templates

type nul > templates\base.html
type nul > templates\login.html
type nul > templates\admin_dashboard.html
type nul > templates\dept_dashboard.html

REM Create venv directory
mkdir venv

echo.
echo Folder structure created successfully!
pause