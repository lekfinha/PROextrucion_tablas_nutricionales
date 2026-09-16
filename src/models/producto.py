"""
Modelo unificado: Producto (nodo del árbol BOM).

Reemplaza SubProducto + ProductoFinal con un solo modelo self-referential.
Un Producto puede contener Ingredientes directos y/o otros Productos como
componentes, permitiendo composición recursiva infinita.

Ejemplo: "Barra de Cereal bañada en chocolate" contiene:
  - "PT Granel" (otro Producto) al 80%
  - "Cobertura Chocolate" (otro Producto) al 20%

Y "PT Granel" contiene:
  - "Extrusión" (Producto) al 70%
  - "Jarabe" (Producto) al 30%

Que a su vez "Extrusión" contiene Ingredientes puros.

Matemática (idéntica al Excel original de Pro Extrusion):

NUTRICIONAL:
  1. Suma ponderada lineal de nutrientes
  2. Humedad ponderada = Σ (proporción × humedad)
  3. Merma = humedad_ponderada − humedad_final
  4. Factor concentración = 1 / (1 − merma)
  5. Nutriente final = suma_lineal × factor

COSTOS:
  1. Costo base = suma ponderada de costos
  2. Cascada secuencial de CostoOperativo
     - Porcentual: costo / (1 − valor)
     - Fijo: costo + valor
"""

from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import (Boolean, DateTime, Date, Float, ForeignKey, Integer,
                         String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.ingrediente import Ingrediente
    from src.models.micronutriente import ProductoMicronutriente


# ──────────────────────────────────────────────────────────────────────────────
# Campos nutricionales que se propagan en el árbol BOM
# Orden: Colesterol agrupado bajo Grasas (RSA Art 115)
# ──────────────────────────────────────────────────────────────────────────────

NUTRIENTES = [
    "energia_kcal",
    "proteinas_g",
    "grasa_total_g",
    "grasa_saturada_g",
    "grasa_monoinsaturada_g",
    "grasa_poliinsaturada_g",
    "acidos_grasos_trans_g",
    "colesterol_mg",
    "carbohidratos_disp_g",
    "azucares_totales_g",
    "sorbitol_g",
    "maltitol_g",
    "fibra_dietetica_g",
    "fibra_soluble_g",
    "fibra_insoluble_g",
    "sodio_mg",
]

# Umbral de declaración de micronutrientes en la tabla nutricional.
# RSA Art 118: se declaran solo los que aportan >= 5% de la DDR por porción.
UMBRAL_DECLARACION_DDR = 5.0

# Etiquetas legibles — colesterol indentado bajo grasas
ETIQUETAS_NUTRIENTES: dict[str, str] = {
    "energia_kcal":             "Energía (kcal)",
    "proteinas_g":              "Proteínas (g)",
    "grasa_total_g":            "Grasa Total (g)",
    "grasa_saturada_g":         "    Grasa Saturada (g)",
    "grasa_monoinsaturada_g":   "    Grasa Monoinsaturada (g)",
    "grasa_poliinsaturada_g":   "    Grasa Poliinsaturada (g)",
    "acidos_grasos_trans_g":    "    Ácidos Grasos Trans (g)",
    "colesterol_mg":            "    Colesterol (mg)",
    "carbohidratos_disp_g":     "H. de Carbono Disponibles (g)",
    "azucares_totales_g":       "    Azúcares Totales (g)",
    "sorbitol_g":               "    Sorbitol (g)",
    "maltitol_g":               "    Maltitol (g)",
    "fibra_dietetica_g":        "Fibra Dietética (g)",
    "fibra_soluble_g":          "    Fibra Soluble (g)",
    "fibra_insoluble_g":        "    Fibra Insoluble (g)",
    "sodio_mg":                 "Sodio (mg)",
}


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: Producto ↔ Ingrediente
# ──────────────────────────────────────────────────────────────────────────────

class RecetaIngrediente(Base):
    """
    Qué fracción (0.0–1.0) de un Ingrediente forma parte de un Producto.
    Ejemplo: Harina de Arroz al 35.75% → proporcion = 0.3575
    """
    __tablename__ = "receta_ingrediente"

    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ingrediente_id: Mapped[int] = mapped_column(
        ForeignKey("ingredientes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    proporcion: Mapped[float] = mapped_column(Float, default=0.0)

    producto: Mapped["Producto"] = relationship(
        back_populates="receta_ingredientes")
    ingrediente: Mapped["Ingrediente"] = relationship()


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: Producto ↔ Producto (self-referential)
# ──────────────────────────────────────────────────────────────────────────────

class RecetaProducto(Base):
    """
    Composición recursiva: un Producto (padre) contiene otro Producto (hijo).
    Ejemplo: "PT Granel" contiene 70% de "Extrusión" y 30% de "Jarabe".
    """
    __tablename__ = "receta_producto"

    padre_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hijo_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    proporcion: Mapped[float] = mapped_column(Float, default=0.0)

    padre: Mapped["Producto"] = relationship(
        "Producto", foreign_keys=[padre_id],
        back_populates="receta_productos",
    )
    hijo: Mapped["Producto"] = relationship(
        "Producto", foreign_keys=[hijo_id],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cascada de Costos Operativos (una sola tabla para todos los productos)
# ──────────────────────────────────────────────────────────────────────────────

class CostoOperativo(Base):
    """
    Un paso en la cascada de costos de un Producto.

    - tipo = "porcentual": costo_nuevo = costo_anterior / (1 − valor)
      Ejemplo: Tamizado pierde 1% → valor = 0.01

    - tipo = "fijo": costo_nuevo = costo_anterior + valor
      Ejemplo: Energía suma $200 CLP/kg → valor = 200
    """
    __tablename__ = "costos_operativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"),
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    producto: Mapped["Producto"] = relationship(
        back_populates="costos_operativos")

    def aplicar(self, costo_entrada: float) -> float:
        """Aplica este paso al costo de entrada y retorna el costo de salida."""
        if self.tipo == "porcentual":
            if self.valor >= 1.0:
                raise ValueError(
                    f"CostoOperativo '{self.nombre}': valor porcentual "
                    f"{self.valor} debe ser < 1.0.")
            return costo_entrada / (1.0 - self.valor)
        elif self.tipo == "fijo":
            return costo_entrada + self.valor
        else:
            raise ValueError(f"Tipo '{self.tipo}' no reconocido.")

    def __repr__(self) -> str:
        return (f"<CostoOperativo '{self.nombre}' tipo={self.tipo} "
                f"valor={self.valor} orden={self.orden}>")


# ──────────────────────────────────────────────────────────────────────────────
# Modelo principal: Producto (nodo unificado del BOM)
# ──────────────────────────────────────────────────────────────────────────────

class Producto(Base):
    """
    Nodo del árbol BOM. Puede ser un SubProducto intermedio o un
    Producto Final terminado. La lógica matemática es idéntica para ambos.

    Un Producto puede estar compuesto por:
    - Ingredientes puros (vía receta_ingredientes)
    - Otros Productos (vía receta_productos) — composición recursiva

    Atributos clave:
    - tipo: "subproducto" | "producto_final" (solo afecta la UI, no la lógica)
    - humedad_final: fracción (0.0–1.0) de humedad post-proceso
    - critico: bool — afecta sellos de advertencia. Auto-detectable.
    """
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, default="")
    tipo: Mapped[str] = mapped_column(String, default="subproducto")
    critico: Mapped[bool] = mapped_column(Boolean, default=False)

    # Datos de etiquetado (relevante para tipo="producto_final")
    porcion_g: Mapped[float] = mapped_column(Float, default=25.0)
    gramaje_g: Mapped[float] = mapped_column(Float, default=200.0)

    # Humedad final post-proceso como fracción (ej: 0.03 = 3%)
    humedad_final: Mapped[float] = mapped_column(Float, default=0.0)

    # Trazabilidad
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False)
    meses_caducidad: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None)

    # ── Relaciones ORM ────────────────────────────────────────────────────────
    receta_ingredientes: Mapped[list[RecetaIngrediente]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )
    receta_productos: Mapped[list[RecetaProducto]] = relationship(
        "RecetaProducto",
        foreign_keys=[RecetaProducto.padre_id],
        back_populates="padre",
        cascade="all, delete-orphan",
    )
    costos_operativos: Mapped[list[CostoOperativo]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="CostoOperativo.orden",
    )
    micronutrientes: Mapped[list["ProductoMicronutriente"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CÁLCULOS NUTRICIONALES
    # ══════════════════════════════════════════════════════════════════════════

    def _humedad_ponderada(self) -> float:
        """Σ (proporción × humedad) de todos los componentes."""
        humedad = 0.0
        for rel in self.receta_ingredientes:
            humedad += rel.proporcion * rel.ingrediente.humedad_porcentaje
        for comp in self.receta_productos:
            humedad += comp.proporcion * comp.hijo.humedad_final
        return humedad

    def merma(self) -> float:
        """merma = humedad_ponderada − humedad_final"""
        return max(0.0, self._humedad_ponderada() - self.humedad_final)

    def factor_concentracion(self) -> float:
        """factor = 1 / (1 − merma)"""
        m = self.merma()
        if m >= 1.0:
            raise ValueError(
                f"Producto '{self.nombre}': merma {m} >= 1.0 es imposible.")
        return 1.0 / (1.0 - m) if m > 0 else 1.0

    def tabla_nutricional_100g(self) -> dict[str, float]:
        """
        Nutrientes por 100g del producto.

        1. Suma ponderada lineal de ingredientes directos
        2. Suma ponderada lineal de productos hijos (sus tablas ya incluyen concentración)
        3. Multiplicar por factor de concentración
        """
        acumulado: dict[str, float] = {n: 0.0 for n in NUTRIENTES}

        for rel in self.receta_ingredientes:
            ing = rel.ingrediente
            for nutriente in NUTRIENTES:
                acumulado[nutriente] += rel.proporcion * getattr(ing, nutriente, 0.0)

        for comp in self.receta_productos:
            hijo_tabla = comp.hijo.tabla_nutricional_100g()
            for nutriente in NUTRIENTES:
                acumulado[nutriente] += comp.proporcion * hijo_tabla[nutriente]

        factor = self.factor_concentracion()
        if factor != 1.0:
            for nutriente in NUTRIENTES:
                acumulado[nutriente] *= factor

        return acumulado

    def tabla_nutricional_porcion(self, porcion_g: float | None = None) -> dict[str, float]:
        """Nutrientes escalados a la porción (default: self.porcion_g)."""
        pg = porcion_g if porcion_g is not None else self.porcion_g
        base = self.tabla_nutricional_100g()
        factor = pg / 100.0
        return {n: v * factor for n, v in base.items()}

    def humedad_porcentaje_display(self) -> float:
        """Humedad final como porcentaje para mostrar en UI."""
        return self.humedad_final * 100.0

    # ══════════════════════════════════════════════════════════════════════════
    # MICRONUTRIENTES DINÁMICOS (RSA Art 118)
    # ══════════════════════════════════════════════════════════════════════════

    def micronutrientes_agregados_100g(self) -> dict[int, dict]:
        """
        Micronutrientes que aporta el árbol BOM, por 100 g de este producto.

        Mismo algoritmo que tabla_nutricional_100g(): suma ponderada de los
        aportes de los ingredientes directos y de los productos hijos, todo
        escalado por el factor de concentración — el agua que se evapora en la
        extrusión concentra las vitaminas y minerales igual que los macros.

        Retorna {micronutriente_id: {"micro": Micronutriente, "cantidad_100g": float}}
        """
        acumulado: dict[int, dict] = {}

        def _sumar(micro, cantidad: float) -> None:
            reg = acumulado.setdefault(
                micro.id, {"micro": micro, "cantidad_100g": 0.0})
            reg["cantidad_100g"] += cantidad

        for rel in self.receta_ingredientes:
            for im in rel.ingrediente.micronutrientes:
                _sumar(im.micronutriente, rel.proporcion * im.cantidad_100g)

        # Los hijos aportan su valor efectivo (BOM + sus propias declaraciones),
        # que ya viene concentrado por el factor del hijo.
        for comp in self.receta_productos:
            for reg in comp.hijo.micronutrientes_efectivos_100g().values():
                _sumar(reg["micro"], comp.proporcion * reg["cantidad_100g"])

        factor = self.factor_concentracion()
        if factor != 1.0:
            for reg in acumulado.values():
                reg["cantidad_100g"] *= factor

        return acumulado

    def micronutrientes_efectivos_100g(self) -> dict[int, dict]:
        """
        Micronutrientes totales por 100 g: lo que aporta el BOM combinado con
        las declaraciones propias del producto (ProductoMicronutriente).

        Regla de combinación:
        - es_adicionado=True  → la declaración es una fortificación y se SUMA
          al aporte nativo de las materias primas.
        - es_adicionado=False → la declaración es un valor medido u oficial
          (ej. análisis de laboratorio) y REEMPLAZA al valor calculado, que
          siempre es una estimación.

        Retorna {micronutriente_id: {"micro", "cantidad_100g", "destacado",
                                     "es_adicionado", "origen"}}
        """
        efectivo: dict[int, dict] = {
            mid: {
                "micro":         reg["micro"],
                "cantidad_100g": reg["cantidad_100g"],
                "destacado":     False,
                "es_adicionado": False,
                "origen":        "bom",
            }
            for mid, reg in self.micronutrientes_agregados_100g().items()
        }

        for pm in self.micronutrientes:
            micro = pm.micronutriente
            nativo = efectivo.get(micro.id, {}).get("cantidad_100g", 0.0)
            efectivo[micro.id] = {
                "micro":         micro,
                "cantidad_100g": (nativo + pm.cantidad_100g if pm.es_adicionado
                                  else pm.cantidad_100g),
                "destacado":     pm.destacado_en_envase,
                "es_adicionado": pm.es_adicionado,
                "origen":        "fortificado" if pm.es_adicionado else "declarado",
            }

        return efectivo

    def tabla_micronutrientes_filtrada(
        self, porcion_g: float | None = None,
    ) -> list[dict]:
        """
        Micronutrientes declarables en la tabla nutricional impresa.

        RSA Art 118: solo se declara un micronutriente si aporta al menos el
        5% de su DDR por porción. Los que quedan por debajo se omiten, salvo
        que estén destacados en el envase (ahí la declaración es obligatoria).

        Fórmula % DDR (RSA Art 115/118):
          ((cantidad_por_100g / 100) * tamaño_porción) / valor_ddr * 100

        Retorna: [{"nombre", "cantidad_100g", "cantidad_porcion",
                   "unidad", "pct_ddr", "destacado", "es_adicionado",
                   "origen"}, ...]  ordenado por el catálogo.
        """
        pg = porcion_g if porcion_g is not None else self.porcion_g
        factor = pg / 100.0
        resultado = []

        for reg in self.micronutrientes_efectivos_100g().values():
            micro = reg["micro"]
            cant_porcion = reg["cantidad_100g"] * factor
            pct_ddr = (cant_porcion / micro.ddr * 100.0) if micro.ddr > 0 else 0.0

            if pct_ddr >= UMBRAL_DECLARACION_DDR or reg["destacado"]:
                resultado.append({
                    "nombre":           micro.nombre,
                    "cantidad_100g":    reg["cantidad_100g"],
                    "cantidad_porcion": cant_porcion,
                    "unidad":           micro.unidad,
                    "pct_ddr":          pct_ddr,
                    "destacado":        reg["destacado"],
                    "es_adicionado":    reg["es_adicionado"],
                    "origen":           reg["origen"],
                })

        resultado.sort(key=lambda r: r["nombre"])
        return resultado

    def evaluar_descriptores_micronutrientes(
        self, porcion_g: float | None = None,
    ) -> list[str]:
        """
        Evalúa descriptores nutricionales legales (RSA Art 120) por porción,
        sobre el valor efectivo (BOM + declaraciones).

        - % DDR >= 20%                        → "Excelente fuente de {nombre}"
        - 10% <= % DDR < 20%                  → "Buena fuente de {nombre}"
        - es_adicionado=True AND % DDR >= 10% → "Fortificado en {nombre}"
        """
        pg = porcion_g if porcion_g is not None else self.porcion_g
        factor = pg / 100.0
        descriptores = []

        for reg in self.micronutrientes_efectivos_100g().values():
            micro = reg["micro"]
            cant_porcion = reg["cantidad_100g"] * factor
            pct_ddr = (cant_porcion / micro.ddr * 100.0) if micro.ddr > 0 else 0.0

            if pct_ddr >= 20.0:
                descriptores.append(f"Excelente fuente de {micro.nombre}")
            elif pct_ddr >= 10.0:
                descriptores.append(f"Buena fuente de {micro.nombre}")

            if reg["es_adicionado"] and pct_ddr >= 10.0:
                descriptores.append(f"Fortificado en {micro.nombre}")

        return sorted(descriptores)

    # ══════════════════════════════════════════════════════════════════════════
    # CÁLCULOS DE COSTOS
    # ══════════════════════════════════════════════════════════════════════════

    def costo_base_kg(self) -> float:
        """Suma ponderada de costos de ingredientes y productos hijos."""
        costo = 0.0
        for rel in self.receta_ingredientes:
            costo += rel.proporcion * rel.ingrediente.costo_kg
        for comp in self.receta_productos:
            costo += comp.proporcion * comp.hijo.costo_final_kg()
        return costo

    def costo_final_kg(self) -> float:
        """Costo final por kg después de la cascada de costos operativos."""
        costo = self.costo_base_kg()
        for paso in self.costos_operativos:
            costo = paso.aplicar(costo)
        return costo

    def costo_por_porcion(self) -> float:
        """Costo de una porción."""
        return self.costo_final_kg() * (self.porcion_g / 1000.0)

    def costo_empaque(self) -> float:
        """Costo del gramaje completo del empaque."""
        return self.costo_final_kg() * (self.gramaje_g / 1000.0)

    # ══════════════════════════════════════════════════════════════════════════
    # CRÍTICO — AUTO-DETECCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def critico_calculado(self) -> bool:
        """
        Auto-detecta si el producto debería ser 'crítico' basándose en
        si algún ingrediente en todo el árbol de receta tiene critico=True.
        """
        for rel in self.receta_ingredientes:
            if rel.ingrediente.critico:
                return True
        for comp in self.receta_productos:
            if comp.hijo.critico_calculado():
                return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # CADUCIDAD — Enfoque mixto (procesos vs. materias primas)
    #
    # La caducidad de un producto procesado la dicta la TECNOLOGÍA DE
    # CONSERVACIÓN y su humedad final, NO el ingrediente más perecedero.
    #
    # - self.meses_caducidad: valor OFICIAL (basado en estudios de vida útil)
    # - caducidad_minima_componentes(): valor SUGERIDO (mín del árbol BOM)
    #   Útil como alerta para subproductos crudos o mezclas sin tratamiento.
    # ══════════════════════════════════════════════════════════════════════════

    def caducidad_minima_componentes(self) -> int | None:
        """
        Recorre todo el árbol BOM y retorna el mínimo de meses_caducidad
        de todos los componentes (ingredientes y productos hijos).

        Útil como SUGERENCIA / ALERTA, no como valor oficial.
        El valor oficial es self.meses_caducidad (asignado por el usuario
        basado en estudios de vida útil reales).

        Retorna None si ningún componente tiene meses_caducidad definido.
        """
        valores: list[int] = []

        for rel in self.receta_ingredientes:
            if rel.ingrediente.meses_caducidad is not None:
                valores.append(rel.ingrediente.meses_caducidad)

        for comp in self.receta_productos:
            # El producto hijo puede tener su propia caducidad oficial
            if comp.hijo.meses_caducidad is not None:
                valores.append(comp.hijo.meses_caducidad)
            # También revisar recursivamente sus componentes
            hijo_min = comp.hijo.caducidad_minima_componentes()
            if hijo_min is not None:
                valores.append(hijo_min)

        return min(valores) if valores else None

    def _recolectar_ingredientes_hoja(self) -> list["Ingrediente"]:
        """Recolecta todos los ingredientes hoja del árbol recursivamente."""
        ingredientes = []
        for rel in self.receta_ingredientes:
            ingredientes.append(rel.ingrediente)
        for comp in self.receta_productos:
            ingredientes.extend(comp.hijo._recolectar_ingredientes_hoja())
        return ingredientes

    def fecha_caducidad_estimada(self) -> date | None:
        """
        Fecha más temprana de vencimiento de fichas técnicas de proveedores.
        Útil para alertar sobre fichas que necesitan renovación.

        Nota: esto NO es la caducidad del producto (que la dicta el proceso),
        es la vigencia de la documentación de los ingredientes.
        """
        ingredientes = self._recolectar_ingredientes_hoja()
        fechas = [ing.fecha_vencimiento_ficha for ing in ingredientes
                  if ing.fecha_vencimiento_ficha is not None]
        return min(fechas) if fechas else None

    def ingredientes_proximos_a_caducar(self, n: int = 5) -> list[tuple]:
        """
        Retorna los `n` ingredientes con fecha de vencimiento de ficha
        técnica más próxima. Útil para gestión de proveedores.

        Cada elemento: (ingrediente, fecha_vencimiento_ficha)
        """
        ingredientes = self._recolectar_ingredientes_hoja()
        con_fecha = [(ing, ing.fecha_vencimiento_ficha) for ing in ingredientes
                     if ing.fecha_vencimiento_ficha is not None]
        con_fecha.sort(key=lambda x: x[1])
        vistos: set[int] = set()
        unicos: list[tuple] = []
        for ing, fecha in con_fecha:
            if ing.id not in vistos:
                vistos.add(ing.id)
                unicos.append((ing, fecha))
        return unicos[:n]

    # ══════════════════════════════════════════════════════════════════════════

    def __repr__(self) -> str:
        return (f"<Producto id={self.id} tipo='{self.tipo}' "
                f"nombre='{self.nombre}'>")
