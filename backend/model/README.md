Put trained model file here after running train.py:
- model.joblib will contain a dict: {"pipeline": <sklearn pipeline>, "meta": {...}}

Train the model by running:
$ python train.py --data sample_data/sample_phishing.csv
This will create model/model.joblib and model/test_predictions.csv
