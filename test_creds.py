import pickle
from google.oauth2.credentials import Credentials

creds = Credentials(token="4/0ASVgi3IRaJUBrCtrUvlKNCL_CqkKHvUGHnYgBlxzE-P7fYNphLkK0NLzx9v8PZE3Ac03ng")  # Временные данные
with open('user_tokens/test.pickle', 'wb') as f:
    pickle.dump(creds, f)