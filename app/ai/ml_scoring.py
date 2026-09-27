import logging
import os
from config.settings import settings

logger = logging.getLogger(__name__)
_model = None
_model_load_attempted = False


def _get_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    path = settings.ML_MODEL_PATH.strip()
    if not path or not os.path.isfile(path):
        return None
    try:
        import xgboost as xgb

        booster = xgb.Booster()
        booster.load_model(path)
        _model = booster
        logger.info("Loaded XGBoost model from %s", path)
    except Exception:
        logger.exception("Failed to load ML model from %s", path)
        _model = None
    return _model


class MLScoringEngine:
    @staticmethod
    def predict_win_probability(features: list) -> tuple[float, str]:
        model = _get_model()
        if model is not None:
            import numpy as np
            import xgboost as xgb

            matrix = np.array([features], dtype=float)
            prob = float(model.predict(xgb.DMatrix(matrix))[0])
            return prob, "xgboost"

        fvg_size = features[2] if len(features) > 2 else 0.0
        vol_delta = features[3] if len(features) > 3 else 1.0
        score = 0.45
        if fvg_size >= 0.30:
            score += 0.12
        if vol_delta > 0.5:
            score += 0.08
        return min(0.85, score), "heuristic_fallback"
