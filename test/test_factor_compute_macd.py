import numpy as np

from core.strategies.utils.factor_compute import FactorCompute


def test_calc_macd_returns_python_mapping():
    close = np.linspace(10.0, 20.0, 80, dtype=np.float32)

    result = FactorCompute.calc_macd(close)

    assert set(result) == {
        "dif", "dea", "macd", "golden_cross", "death_cross",
    }
    assert result["dif"].shape == (80, 1)
    assert result["golden_cross"].dtype == np.bool_
