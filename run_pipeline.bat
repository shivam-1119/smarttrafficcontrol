@echo off
title Smart Traffic Prediction Model
echo =======================================================
echo     Smart Traffic Control - Prediction Pipeline
echo =======================================================
echo.
echo Installing requirements (if any are missing)...
pip install pandas numpy scikit-learn matplotlib xgboost
echo.
echo Running the pipeline...
"C:\Users\shivam\AppData\Local\Programs\Python\Python313\python.exe" traffic_prediction_pipeline.py
echo.
echo Pipeline finished! Check the folder for the generated plot.
pause
