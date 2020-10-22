import json
from decimal import Decimal


class PandasJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, int):
            return int(o)
        elif isinstance(o, float):
            return float(o)
        elif isinstance(o, Decimal):
            if '.' in str(o):
                return float(o)
            else:
                return int(o)
        else:
            return super().default(o)
