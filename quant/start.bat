@echo off

:menu
echo ===============================================
echo          Quant Data Processing System          
echo ===============================================
echo 1. Run full process (main.py + combined.py)
echo 2. Run data crawling only (main.py)
echo 3. Run data processing only (combined.py)
echo 4. Exit
echo ===============================================
set /p choice=Please enter your choice (1-4): 

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_main
if "%choice%"=="3" goto run_combined
if "%choice%"=="4" goto exit

echo Invalid choice, please try again!
echo.
goto menu

:run_all
echo.
echo ===============================================
echo              Starting full process                
echo ===============================================
echo 1. Running data crawling script (main.py)...
python main.py
echo.
echo 2. Running data processing script (combined.py)...
python combined.py
echo.
echo ===============================================
echo               Full process completed               
echo ===============================================
goto end

:run_main
echo.
echo ===============================================
echo            Running data crawling script              
echo ===============================================
python main.py
echo.
echo ===============================================
echo              Data crawling completed                
echo ===============================================
goto end

:run_combined
echo.
echo ===============================================
echo            Running data processing script              
echo ===============================================
python combined.py
echo.
echo ===============================================
echo              Data processing completed                
echo ===============================================
goto end

:exit
echo.
echo Thank you for using, goodbye!
goto end

:end
echo.
pause