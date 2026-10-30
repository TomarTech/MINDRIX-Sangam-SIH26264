import pandas as pd

# Single "today" used by every page. Real date, so new actions and alerts agree.
TODAY = pd.Timestamp.today().normalize()