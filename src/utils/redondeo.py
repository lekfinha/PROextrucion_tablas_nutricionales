"""
Redondeo Minsal — RSA Art 115.

Regla de redondeo para la tabla nutricional:
  ≥ 100     → entero (sin decimales)
  10 – 99.9 → 1 decimal
  < 10      → 2 decimales (incluye valores < 1)

La aproximación: si el dígito a descartar ≥ 5, se sube el anterior.
Se usa ROUND_HALF_UP (no el banker's rounding de Python por defecto).
"""

from decimal import Decimal, ROUND_HALF_UP


def redondear_minsal(valor: float) -> str:
    """
    Aplica la regla de redondeo del RSA Art 115 a un valor nutricional.

    Retorna un string formateado (listo para mostrar en la tabla).

    Ejemplos:
        redondear_minsal(383.676) → "384"
        redondear_minsal(10.493)  → "10.5"
        redondear_minsal(2.007)   → "2.01"
        redondear_minsal(0.218)   → "0.22"
        redondear_minsal(0.0)     → "0.00"
    """
    d = Decimal(str(valor))

    if valor >= 100:
        result = d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return str(int(result))
    elif valor >= 10:
        result = d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return str(result)
    else:
        result = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return str(result)
