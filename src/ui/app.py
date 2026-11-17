"""
Interfaz gráfica principal — Gestor Nutricional Pro Extrusion.

Usa el modelo unificado Producto: no hay distinción entre producto
intermedio y terminado, cualquiera puede etiquetarse o componer a otro.
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from src.database import engine
from src.models.ingrediente import Ingrediente
from src.models.producto import (Producto, RecetaIngrediente, RecetaProducto,
                                  CostoOperativo, NUTRIENTES, ETIQUETAS_NUTRIENTES)
from src.models.micronutriente import (Micronutriente, ProductoMicronutriente,
                                        IngredienteMicronutriente)
from src.normativas import calcular_sellos, listar_normativas
from src.etiquetado import (consolidar_etiquetado, DECLARABLES, SIN_CODES,
                            REQUERIMIENTOS, CODIGOS_FENILALANINA,
                            TIPO_ALERGENO, TIPO_COLORANTE, TIPO_EDULCORANTE,
                            TIPO_POLIALCOHOL, TIPO_ADVERTENCIA, TIPO_TRAZA)
from src.utils.redondeo import redondear_minsal

# ── Paleta y fuentes ───────────────────────────────────────────────────────────
COLOR_BG     = "#F5F5F5"
COLOR_ACENTO = "#2C7BE5"
COLOR_PELIGRO= "#E53935"
COLOR_EXITO  = "#43A047"
COLOR_TEXTO  = "#212121"
COLOR_WARN   = "#FF8F00"
FONT_TITULO  = ("Segoe UI", 15, "bold")
FONT_NORMAL  = ("Segoe UI", 10)
FONT_PEQUEÑA = ("Segoe UI", 9)
FONT_BOLD    = ("Segoe UI", 10, "bold")


class AppNutricion(tk.Tk):
    """Aplicación principal — Gestor Nutricional Pro Extrusion."""

    def __init__(self):
        super().__init__()
        self.title("Gestor Nutricional — Pro Extrusion")
        self.geometry("760x800")
        self.minsize(560, 640)
        self.config(bg=COLOR_BG)
        self.resizable(True, True)

        # ── Campos del formulario de Ingredientes ──
        self.campos_formulario = {
            "nombre":                 ("Nombre del Ingrediente",         str),
            "fabricante":             ("Fabricante / Proveedor",         str),
            "costo_kg":               ("Costo por Kg ($)",               float),
            "energia_kcal":           ("Energía (Kcal/100g)",            float),
            "proteinas_g":            ("Proteínas (g/100g)",             float),
            "grasa_total_g":          ("Grasa Total (g)",                float),
            "grasa_saturada_g":       ("  └ Grasa Saturada (g)",         float),
            "grasa_monoinsaturada_g": ("  └ Grasa Monoinsat. (g)",       float),
            "grasa_poliinsaturada_g": ("  └ Grasa Poliinsat. (g)",       float),
            "acidos_grasos_trans_g":  ("  └ Ácidos Grasos Trans (g)",    float),
            "colesterol_mg":          ("  └ Colesterol (mg)",            float),
            "carbohidratos_disp_g":   ("H. de Carbono Disp. (g)",        float),
            "azucares_totales_g":     ("  └ Azúcares Totales (g)",       float),
            "sorbitol_g":             ("  └ Sorbitol (g)",               float),
            "maltitol_g":             ("  └ Maltitol (g)",               float),
            "fibra_dietetica_g":      ("Fibra Dietética (g)",            float),
            "fibra_soluble_g":        ("  └ Fibra Soluble (g)",          float),
            "fibra_insoluble_g":      ("  └ Fibra Insoluble (g)",        float),
            "sodio_mg":               ("Sodio (mg)",                     float),
            "humedad_porcentaje":     ("Humedad (%, ej: 7.0)",           float),
        }
        self._campos_en_fraccion = {"humedad_porcentaje"}

        self.entries: dict[str, tk.Entry] = {}
        # Checkboxes de etiquetado del ingrediente: {código → BooleanVar}
        self._declarable_vars: dict[str, tk.BooleanVar] = {}
        self._req_vars: dict[str, tk.BooleanVar] = {}
        self._cafeina_var = tk.BooleanVar(value=False)
        # Entries de micronutrientes del ingrediente: {micronutriente_id: Entry}
        self._entries_micro: dict[int, tk.Entry] = {}
        self._nombres_micro: dict[int, str] = {}
        self.mapa_ingredientes: dict[str, int] = {}
        self.mapa_productos:    dict[str, int] = {}
        self.ingrediente_actual_id: int | None = None
        self._critico_var = tk.BooleanVar(value=False)

        self.container = tk.Frame(self, bg=COLOR_BG)
        self.container.pack(fill="both", expand=True)
        self.mostrar_menu_principal()

    # ══════════════════════════════════════════════════════════════════════════
    # UTILIDADES GENERALES
    # ══════════════════════════════════════════════════════════════════════════

    def limpiar_pantalla(self):
        for w in self.container.winfo_children():
            w.destroy()
        self.entries.clear()
        self._declarable_vars.clear()
        self._req_vars.clear()
        self._entries_micro.clear()
        self._nombres_micro.clear()
        self.ingrediente_actual_id = None

    def _titulo(self, parent, texto):
        lbl = tk.Label(parent, text=texto, font=FONT_TITULO, bg=COLOR_BG, fg=COLOR_TEXTO)
        lbl.pack(pady=(16, 8))
        return lbl

    def _boton(self, parent, texto, comando,
               color_bg="#E0E0E0", color_fg=COLOR_TEXTO, ancho=28):
        return tk.Button(parent, text=texto, command=comando,
                         bg=color_bg, fg=color_fg, font=FONT_NORMAL,
                         width=ancho, relief="flat", cursor="hand2",
                         activebackground=color_bg, activeforeground=color_fg,
                         pady=6)

    def _separador(self, parent):
        tk.Frame(parent, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=6)

    def _crear_scroll_frame(self, parent):
        outer = tk.Frame(parent, bg=COLOR_BG)
        canvas = tk.Canvas(outer, bg=COLOR_BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLOR_BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        # La rueda se liga a esta ventana y no con bind_all: si no, el último
        # canvas creado (p.ej. el de la tabla nutricional) se queda con la
        # rueda de toda la app y el formulario de atrás deja de scrollear.
        raiz = parent.winfo_toplevel()
        raiz.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        raiz.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        raiz.bind("<MouseWheel>",
                  lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return outer, inner, canvas

    def _barra_botones(self, volver_cmd, guardar_cmd, guardar_texto="💾  Guardar"):
        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(frame, "← Volver", volver_cmd, ancho=14).pack(side="left", padx=(0, 6))
        self._boton(frame, guardar_texto, guardar_cmd,
                    color_bg=COLOR_EXITO, color_fg="white", ancho=22).pack(side="right")
        return frame

    def _combobox_buscable(self, parent, opciones, callback):
        var = tk.StringVar()
        combo = ttk.Combobox(parent, textvariable=var, width=45, font=FONT_NORMAL)
        combo['values'] = opciones

        def _filter(event):
            if event.keysym in ("Down", "Up", "Return", "Escape"):
                return
            texto = var.get().lower().strip()
            filtradas = [o for o in opciones if texto in o.lower()] if texto else opciones
            combo['values'] = filtradas
            if filtradas:
                try:
                    combo.tk.eval(f"ttk::combobox::Post {combo}")
                except Exception:
                    pass

        combo.bind('<KeyRelease>', _filter)
        combo.bind('<<ComboboxSelected>>', callback)
        return combo

    def _recargar_mapa_ingredientes(self):
        with Session(engine) as s:
            ings = s.query(Ingrediente).order_by(Ingrediente.nombre).all()
            self.mapa_ingredientes = {ing.id_unico: ing.id for ing in ings}

    def _crear_combobox_buscable(self, parent, callback):
        self._recargar_mapa_ingredientes()
        return self._combobox_buscable(parent, sorted(self.mapa_ingredientes), callback)

    def _recargar_mapa_productos(self):
        with Session(engine) as s:
            q = s.query(Producto).order_by(Producto.nombre)
            prods = q.all()
            self.mapa_productos = {p.nombre: p.id for p in prods}

    def _crear_combobox_producto(self, parent, callback):
        self._recargar_mapa_productos()
        return self._combobox_buscable(parent, sorted(self.mapa_productos), callback)

    def _selectinload_completo(self):
        """Carga eager completa para calcular tabla nutricional recursiva."""
        return [
            selectinload(Producto.receta_ingredientes)
                .selectinload(RecetaIngrediente.ingrediente),
            selectinload(Producto.receta_productos)
                .selectinload(RecetaProducto.hijo)
                .selectinload(Producto.receta_ingredientes)
                .selectinload(RecetaIngrediente.ingrediente),
            selectinload(Producto.receta_productos)
                .selectinload(RecetaProducto.hijo)
                .selectinload(Producto.costos_operativos),
            selectinload(Producto.costos_operativos),
            selectinload(Producto.micronutrientes)
                .selectinload(ProductoMicronutriente.micronutriente),
            selectinload(Producto.receta_productos)
                .selectinload(RecetaProducto.hijo)
                .selectinload(Producto.micronutrientes)
                .selectinload(ProductoMicronutriente.micronutriente),
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # VENTANA TABLA NUTRICIONAL + SELLOS
    # ══════════════════════════════════════════════════════════════════════════

    def _construir_desglose_caducidad(self, parent, prod_id, expandido=False):
        """
        Resumen de vida útil + lista (de menor a mayor semanas) de los componentes
        directos del producto. Doble clic en un producto baja un nivel.
        La lista se despliega al hacer clic en la vida útil.
        """
        with Session(engine) as s:
            p = s.get(Producto, prod_id)
            efectiva = p.semanas_caducidad_efectiva()
            calculada = p.semanas_caducidad_calculada()
            override = p.semanas_caducidad_override
            comps = p.componentes_caducidad()

        fmt = lambda v: f"{v} sem" if v is not None else "sin dato"
        txt = f"Vida útil: {fmt(efectiva)}"
        color = "#555555"
        if override is not None:
            txt += f"  (manual; calculada por componentes: {fmt(calculada)})"
            if calculada is not None and override > calculada:
                txt += "  ⚠️ mayor que el componente más corto"
                color = COLOR_WARN
        else:
            txt += "  (calculada por componentes)"
        lbl = tk.Label(parent, text=txt, font=FONT_BOLD, bg=COLOR_BG, fg=color,
                       cursor="hand2" if comps else "")
        lbl.pack(pady=(4, 2))
        if not comps:
            return

        cuerpo = tk.Frame(parent, bg=COLOR_BG)
        estado = {"abierto": False}

        def alternar(_event=None):
            estado["abierto"] = not estado["abierto"]
            if estado["abierto"]:
                cuerpo.pack(fill="x", after=lbl)
            else:
                cuerpo.pack_forget()
            lbl.config(text=("▼ " if estado["abierto"] else "▶ ") + txt)

        lbl.bind("<Button-1>", alternar)
        frame = tk.Frame(cuerpo, bg=COLOR_BG)
        frame.pack(fill="x", padx=20)
        tree = ttk.Treeview(frame, columns=("tipo", "nombre", "sem"),
                            show="headings", height=min(max(len(comps), 2), 6))
        tree.heading("tipo", text="Tipo")
        tree.heading("nombre", text="Componente (↓ menor duración)")
        tree.heading("sem", text="Semanas")
        tree.column("tipo", width=90, anchor="center")
        tree.column("nombre", width=380)
        tree.column("sem", width=90, anchor="center")
        tree.pack(fill="x")
        destinos = {}
        for c in comps:
            es_prod = c["tipo"] == "producto"
            iid = tree.insert("", "end", values=(
                "Producto ▸" if es_prod else "Ingrediente", c["nombre"],
                c["semanas"] if c["semanas"] is not None else "—"))
            if es_prod:
                destinos[iid] = (c["id"], c["nombre"])

        def bajar(_event):
            sel = tree.selection()
            if sel and sel[0] in destinos:
                pid, nombre = destinos[sel[0]]
                win = tk.Toplevel(self)
                win.title(f"Desglose de caducidad — {nombre}")
                win.config(bg=COLOR_BG)
                win.geometry("560x340")
                tk.Label(win, text=nombre, font=FONT_TITULO, bg=COLOR_BG).pack(pady=(12, 2))
                self._construir_desglose_caducidad(win, pid, expandido=True)
        tree.bind("<Double-1>", bajar)
        tk.Label(cuerpo, text="Doble clic en un Producto ▸ para ver sus componentes.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack()
        lbl.config(text="▶ " + txt)
        if expandido:
            alternar()

    def _acordeon(self, parent, resumen, color="#555555", abierto=False):
        """Título clicable + frame plegable. Retorna el frame del contenido."""
        lbl = tk.Label(parent, text="▶ " + resumen, font=FONT_BOLD, bg=COLOR_BG,
                       fg=color, cursor="hand2")
        lbl.pack(anchor="w")
        cuerpo = tk.Frame(parent, bg=COLOR_BG)
        estado = {"abierto": False}

        def alternar(_event=None):
            estado["abierto"] = not estado["abierto"]
            if estado["abierto"]:
                cuerpo.pack(fill="x", after=lbl)
            else:
                cuerpo.pack_forget()
            lbl.config(text=("▼ " if estado["abierto"] else "▶ ") + resumen)

        lbl.bind("<Button-1>", alternar)
        if abierto:
            alternar()
        return cuerpo

    def _texto_con_negritas(self, parent, markdown, alto=3):
        """
        Pinta un string con **negritas** en un Text de solo lectura.
        Text y no Label porque la lista de ingredientes se copia tal cual al
        arte de la etiqueta, y así el usuario puede seleccionarla.
        """
        txt = tk.Text(parent, height=alto, wrap="word", font=FONT_NORMAL,
                      bg="#FFFFFF", fg=COLOR_TEXTO, relief="solid", bd=1,
                      padx=6, pady=4)
        txt.tag_configure("negrita", font=FONT_BOLD)
        for trozo in re.split(r"(\*\*[^*]+\*\*)", markdown):
            if not trozo:
                continue
            if trozo.startswith("**") and trozo.endswith("**"):
                txt.insert("end", trozo[2:-2], "negrita")
            else:
                txt.insert("end", trozo)
        txt.config(state="disabled")
        txt.pack(fill="x", padx=20, pady=(2, 0))
        return txt

    def _construir_bloque_etiquetado(self, parent, ficha):
        """
        Lista de ingredientes aplanada (tabla + string listo para el arte),
        «Contiene:» en negrilla y cuerpo mayor, trazas en párrafo aparte y
        desglose desplegable de requerimientos alimentarios.
        """
        tk.Frame(parent, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=4)
        marco = tk.Frame(parent, bg=COLOR_BG)
        marco.pack(fill="x", padx=15, pady=(0, 4))

        resumen = (f"Ingredientes (RSA Art 107): {len(ficha.ingredientes)} "
                   f"materias primas — total {ficha.total_porcentaje:.2f}%")
        color = COLOR_WARN if abs(ficha.total_porcentaje - 100.0) > 0.01 else "#555555"
        cuerpo = self._acordeon(marco, resumen, color)

        tree = ttk.Treeview(cuerpo, columns=("ing", "pct", "al"),
                            show="headings",
                            height=min(max(len(ficha.ingredientes), 2), 10))
        tree.heading("ing", text="Ingrediente (↓ mayor cantidad)")
        tree.heading("pct", text="%")
        tree.heading("al", text="Declara")
        tree.column("ing", width=380)
        tree.column("pct", width=80, anchor="center")
        tree.column("al", width=200)
        tree.tag_configure("con_alergeno", foreground="#C62828")
        tree.pack(fill="x", padx=20)
        for linea in ficha.ingredientes:
            marcas = ", ".join(DECLARABLES.get(c, (c, ""))[0] for c in linea.declarables)
            tree.insert("", "end", values=(linea.nombre, f"{linea.porcentaje:.3f}", marcas),
                        tags=("con_alergeno",) if marcas else ())

        # String listo para el arte: orden decreciente, colorantes/edulcorantes
        # en negrilla, alérgenos entre paréntesis, cerrado por las leyendas
        # obligatorias y las trazas — el párrafo completo de la etiqueta.
        tk.Label(marco, text="Lista para el envase:", font=FONT_PEQUEÑA,
                 bg=COLOR_BG, fg="#757575").pack(anchor="w", pady=(6, 0))
        self._texto_con_negritas(marco, ficha.texto_ingredientes())

        # «Contiene:» — negrilla y cuerpo mayor, como exige la rotulación
        for texto in (ficha.texto_contiene(), ficha.texto_colorantes()):
            if texto:
                tk.Label(marco, text=texto, font=("Segoe UI", 12, "bold"),
                         bg=COLOR_BG, fg="#C62828", wraplength=680,
                         justify="left").pack(anchor="w", pady=(4, 0))

        # Desglose sanitario: solo lo que el árbol realmente activó
        cuerpo_al = self._acordeon(
            marco,
            (f"Desglose sanitario: {len(ficha.alertas)} declaraciones"
             if ficha.alertas else "Desglose sanitario: ninguna declaración"),
            "#C62828" if ficha.alertas else "#43A047")

        if not ficha.alertas:
            tk.Label(cuerpo_al,
                     text=("✓ Libre de alérgenos, colorantes destacados, "
                           "edulcorantes, polialcoholes y trazas declarables"),
                     font=FONT_NORMAL, bg=COLOR_BG, fg="#43A047").pack(anchor="w", padx=20)
        else:
            tree_al = ttk.Treeview(cuerpo_al, columns=("qué", "tipo", "quién"),
                                   show="headings", height=len(ficha.alertas))
            tree_al.heading("qué", text="Alérgeno / Aditivo")
            tree_al.heading("tipo", text="Tipo de Declaración")
            tree_al.heading("quién", text="Ingredientes que lo contienen")
            # "qué" ancha porque las trazas y leyendas son frases completas
            tree_al.column("qué", width=240)
            tree_al.column("tipo", width=190, anchor="center")
            tree_al.column("quién", width=250)
            tree_al.tag_configure(TIPO_ALERGENO, foreground="#C62828")
            tree_al.tag_configure(TIPO_COLORANTE, foreground="#AD1457")
            tree_al.tag_configure(TIPO_EDULCORANTE, foreground="#6A1B9A")
            tree_al.tag_configure(TIPO_POLIALCOHOL, foreground="#EF6C00")
            tree_al.tag_configure(TIPO_ADVERTENCIA, foreground="#B71C1C")
            tree_al.tag_configure(TIPO_TRAZA, foreground="#757575")
            tree_al.pack(fill="x", padx=20)
            for a in ficha.alertas:
                tree_al.insert("", "end", tags=(a.tipo,),
                               values=(a.nombre, a.etiqueta_tipo,
                                       ", ".join(a.responsables)))

        # Desglose de requerimientos: qué se cumple y, si no, quién lo impide
        n_cumple = sum(1 for k in REQUERIMIENTOS if ficha.cumple(k))
        cuerpo_req = self._acordeon(
            marco, f"Requerimientos alimentarios: {n_cumple}/{len(REQUERIMIENTOS)} se cumplen",
            "#43A047" if n_cumple else "#757575")

        tree_req = ttk.Treeview(cuerpo_req, columns=("req", "estado", "culpa"),
                                show="headings", height=len(REQUERIMIENTOS))
        tree_req.heading("req", text="Requisito alimentario")
        tree_req.heading("estado", text="Estado")
        tree_req.heading("culpa", text="Ingredientes que no cumplen")
        tree_req.column("req", width=170)
        tree_req.column("estado", width=110, anchor="center")
        tree_req.column("culpa", width=380)
        tree_req.tag_configure("si", foreground="#43A047")
        tree_req.tag_configure("no", foreground="#C62828")
        tree_req.pack(fill="x", padx=20)
        for campo, etiqueta in REQUERIMIENTOS.items():
            cumple = ficha.cumple(campo)
            culpables = ", ".join(ficha.requerimientos.get(campo, []))
            tree_req.insert("", "end", tags=("si" if cumple else "no",),
                            values=(etiqueta,
                                    "SÍ CUMPLE" if cumple else "NO CUMPLE",
                                    "—" if cumple else (culpables or "sin ingredientes")))

    def _mostrar_toplevel_nutricional(self, titulo_ventana, nombre_producto,
                                      tabla_100g, tabla_porcion,
                                      porcion_g, merma_pct, factor, costo_kg,
                                      critico=False, critico_auto=False,
                                      humedad_final_pct=0.0,
                                      micronutrientes=None,
                                      descriptores=None,
                                      caducidad_info=None,
                                      ficha=None):
        top = tk.Toplevel(self)
        top.title(titulo_ventana)
        top.geometry("740x900")
        top.config(bg=COLOR_BG)
        top.resizable(True, True)

        # Todo el contenido va dentro del frame con scroll: con la lista de
        # ingredientes y el desglose de requerimientos ya no cabe en pantalla.
        outer, cuerpo, _ = self._crear_scroll_frame(top)
        outer.pack(fill="both", expand=True)

        tk.Label(cuerpo, text=nombre_producto, font=FONT_TITULO, bg=COLOR_BG).pack(pady=(14, 2))

        # ── Cabecera: información de proceso (humedad separada) ──
        info_proceso = (f"Humedad: {humedad_final_pct:.2f}%  |  "
                        f"Concentración: {merma_pct:.4f}%  |  Factor: ×{factor:.5f}")
        tk.Label(cuerpo, text=info_proceso, font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#555555").pack()

        crit_txt = "Sí" if critico else "No"
        if critico != critico_auto:
            crit_txt += f"  ⚠️ (auto-detección sugiere {'Sí' if critico_auto else 'No'})"
        info_negocio = f"Crítico: {crit_txt}  |  Costo final: ${costo_kg:,.2f} /kg"
        tk.Label(cuerpo, text=info_negocio, font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#555555").pack()

        # ── Caducidad en cascada (semanas) + desglose navegable ──
        if caducidad_info:
            self._construir_desglose_caducidad(cuerpo, caducidad_info["prod_id"])

        tk.Frame(cuerpo, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=8)

        # ── Tabla nutricional con redondeo Minsal ──
        frame_tree = tk.Frame(cuerpo, bg=COLOR_BG)
        frame_tree.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        col_p = f"Por {porcion_g:.0f} g"
        tree = ttk.Treeview(frame_tree, columns=("nut", "c100", "cpor"),
                            show="headings")
        tree.heading("nut", text="Nutriente")
        tree.heading("c100", text="Por 100 g")
        tree.heading("cpor", text=col_p)
        tree.column("nut",  width=295)
        tree.column("c100", width=120, anchor="center")
        tree.column("cpor", width=120, anchor="center")

        tree.pack(fill="x", expand=True)

        for key in NUTRIENTES:
            label = ETIQUETAS_NUTRIENTES.get(key, key)
            v100 = tabla_100g.get(key, 0.0)
            vpor = tabla_porcion.get(key, 0.0)
            tree.insert("", "end", values=(
                label, redondear_minsal(v100), redondear_minsal(vpor)))

        # ── Micronutrientes filtrados ──
        if micronutrientes:
            tree.insert("", "end", values=("", "", ""))
            tree.insert("", "end", values=("── Micronutrientes ──", "", ""))
            for mn in micronutrientes:
                marcas = ""
                if mn.get("destacado"):
                    marcas += " ★"
                if mn.get("es_adicionado"):
                    marcas += " ⊕"
                label = f"    {mn['nombre']} ({mn['unidad']}){marcas}"
                tree.insert("", "end", values=(
                    label,
                    redondear_minsal(mn["cantidad_100g"]),
                    f"{redondear_minsal(mn['cantidad_porcion'])} ({mn['pct_ddr']:.1f}% DDR)"))

        tree.config(height=len(tree.get_children()))

        # ── Lista de ingredientes aplanada + alérgenos (RSA Art 107) ──
        if ficha is not None:
            self._construir_bloque_etiquetado(cuerpo, ficha)

        # ── Descriptores nutricionales (RSA Art 120) ──
        if descriptores:
            tk.Frame(cuerpo, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=4)
            frame_desc = tk.Frame(cuerpo, bg=COLOR_BG)
            frame_desc.pack(fill="x", padx=15, pady=(0, 4))
            tk.Label(frame_desc, text="Descriptores Nutricionales (RSA Art 120):",
                     font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_ACENTO).pack(anchor="w")
            for desc in descriptores:
                color = "#1565C0" if "Excelente" in desc or "Fortificado" in desc else "#43A047"
                tk.Label(frame_desc, text=f"  ✓ {desc}",
                         font=FONT_NORMAL, bg=COLOR_BG, fg=color).pack(anchor="w")

        # ── Sección de sellos / destacadores ──
        tk.Frame(cuerpo, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=4)
        frame_norm = tk.Frame(cuerpo, bg=COLOR_BG)
        frame_norm.pack(fill="x", padx=15, pady=(0, 4))

        tk.Label(frame_norm, text="Normativa:", font=FONT_NORMAL, bg=COLOR_BG).pack(side="left")
        normativas = listar_normativas()
        norm_var = tk.StringVar()
        combo_norm = ttk.Combobox(frame_norm, textvariable=norm_var,
                                  values=normativas, state="readonly",
                                  width=38, font=FONT_NORMAL)
        combo_norm.pack(side="left", padx=6)
        if normativas:
            combo_norm.current(0)

        frame_sellos = tk.Frame(cuerpo, bg=COLOR_BG)
        frame_sellos.pack(fill="both", expand=False, padx=15, pady=(0, 10))

        tree_sellos = ttk.Treeview(frame_sellos,
            columns=("cat", "nombre", "resultado"), show="headings", height=10)
        tree_sellos.heading("cat", text="Tipo")
        tree_sellos.heading("nombre", text="Indicador")
        tree_sellos.heading("resultado", text="Resultado")
        tree_sellos.column("cat", width=100, anchor="center")
        tree_sellos.column("nombre", width=250)
        tree_sellos.column("resultado", width=200, anchor="center")
        tree_sellos.pack(fill="x", expand=True)

        tree_sellos.tag_configure("sello_si", foreground="#C62828")
        tree_sellos.tag_configure("sello_no", foreground="#43A047")
        tree_sellos.tag_configure("dest_si", foreground="#1565C0")
        tree_sellos.tag_configure("dest_no", foreground="#9E9E9E")

        def _actualizar_sellos(*_args):
            for item in tree_sellos.get_children():
                tree_sellos.delete(item)
            nombre_norm = norm_var.get()
            if not nombre_norm:
                return
            sellos = calcular_sellos(nombre_norm, tabla_100g, tabla_porcion, critico)
            for s in sellos:
                resultado = s["resultado"] or "—"
                if s["categoria"] == "Sello":
                    tag = "sello_si" if "Con" in resultado else "sello_no"
                else:
                    tag = "dest_si" if resultado and resultado != "—" else "dest_no"
                tree_sellos.insert("", "end",
                    values=(s["categoria"], s["nombre"], resultado), tags=(tag,))

        combo_norm.bind("<<ComboboxSelected>>", _actualizar_sellos)
        if normativas:
            _actualizar_sellos()

    # ══════════════════════════════════════════════════════════════════════════
    # MENÚ PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_principal(self):
        """
        Explorador en árbol — pantalla de inicio. Reemplaza el viejo menú de
        tres botones: Ingredientes, Productos (divididos en Vendibles / Uso
        Interno) y Normativas conviven como carpetas de un mismo árbol.
        """
        self.limpiar_pantalla()
        self._seleccion_actual: tuple[str, int | None] | None = None

        barra = tk.Frame(self.container, bg=COLOR_BG)
        barra.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(barra, text="🔍", bg=COLOR_BG, font=FONT_NORMAL).pack(side="left")
        self._e_buscar_arbol = tk.Entry(barra, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_buscar_arbol.pack(side="left", fill="x", expand=True, padx=(4, 10))
        self._e_buscar_arbol.bind("<KeyRelease>", self._filtrar_arbol)

        self._boton(barra, "➕ Ingrediente", lambda: self.mostrar_formulario("crear_nuevo"),
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=15).pack(side="left", padx=2)
        self._boton(barra, "➕ Producto", lambda: self.mostrar_formulario_producto("crear"),
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=13).pack(side="left", padx=2)
        self._boton(barra, "🗑️ Eliminar", self._eliminar_seleccionado,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=12).pack(side="left", padx=2)

        self._separador(self.container)

        frame_tree = tk.Frame(self.container, bg=COLOR_BG)
        frame_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._tree_explorador = ttk.Treeview(frame_tree, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(frame_tree, orient="vertical", command=self._tree_explorador.yview)
        self._tree_explorador.configure(yscrollcommand=sb.set)
        self._tree_explorador.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._tree_explorador.bind("<<TreeviewSelect>>", self._on_seleccion_arbol)
        self._tree_explorador.bind("<Double-1>", self._on_abrir_arbol)
        self._tree_explorador.bind("<Return>", self._on_abrir_arbol)

        self._poblar_arbol()

    def _poblar_arbol(self, filtro: str = ""):
        """
        Reconstruye el árbol completo. Con filtro, las carpetas que tengan
        coincidencias quedan expandidas automáticamente; sin filtro, el árbol
        arranca colapsado para no saturar la pantalla.
        """
        tree = self._tree_explorador
        tree.delete(*tree.get_children())
        # iid del árbol → (tipo, id). Las carpetas no se registran: el
        # default ("carpeta", None) de .get() ya las cubre.
        self._tree_nodos: dict[str, tuple[str, int | None]] = {}
        f = filtro.strip().lower()

        nodo_ing = tree.insert("", "end", text="📦 Ingredientes", open=bool(f))
        with Session(engine) as s:
            for ing in s.query(Ingrediente).order_by(Ingrediente.nombre).all():
                if f and f not in ing.nombre.lower() and f not in (ing.fabricante or "").lower():
                    continue
                iid = tree.insert(nodo_ing, "end", text=f"{ing.nombre} — {ing.fabricante}")
                self._tree_nodos[iid] = ("ingrediente", ing.id)

        nodo_prod = tree.insert("", "end", text="🧪 Productos", open=bool(f))
        nodo_vend = tree.insert(nodo_prod, "end", text="✅ Productos Vendibles", open=bool(f))
        nodo_interno = tree.insert(nodo_prod, "end", text="🔧 Preparaciones / Uso Interno",
                                   open=bool(f))
        with Session(engine) as s:
            for p in s.query(Producto).order_by(Producto.nombre).all():
                if f and f not in p.nombre.lower():
                    continue
                raiz = nodo_vend if p.es_vendible else nodo_interno
                iid = tree.insert(raiz, "end", text=p.nombre)
                self._tree_nodos[iid] = ("producto", p.id)

        nodo_norm = tree.insert("", "end", text="📋 Normativas")
        self._tree_nodos[nodo_norm] = ("normativas", None)

    def _filtrar_arbol(self, event=None):
        self._poblar_arbol(self._e_buscar_arbol.get())

    def _on_seleccion_arbol(self, event=None):
        """Solo guarda qué quedó seleccionado — el botón Eliminar lo usa."""
        sel = self._tree_explorador.selection()
        self._seleccion_actual = (self._tree_nodos.get(sel[0], ("carpeta", None))
                                  if sel else None)

    def _on_abrir_arbol(self, event=None):
        """Doble clic / Enter sobre un ítem: abre su vista de detalle."""
        sel = self._tree_explorador.selection()
        if not sel:
            return
        kind, id_ = self._tree_nodos.get(sel[0], ("carpeta", None))
        if kind == "ingrediente":
            self.mostrar_detalle_ingrediente(id_)
        elif kind == "producto":
            self.mostrar_detalle_producto(id_)
        elif kind == "normativas":
            self.mostrar_vista_normativas_vacia()

    def _eliminar_seleccionado(self):
        """Botón global de la barra superior: borra lo que esté seleccionado en el árbol."""
        sel = self._seleccion_actual
        if not sel or sel[0] not in ("ingrediente", "producto"):
            messagebox.showinfo("Eliminar",
                                "Selecciona un Ingrediente o Producto en el árbol primero.")
            return
        kind, id_ = sel
        etiqueta = "Ingrediente" if kind == "ingrediente" else "Producto"
        if not messagebox.askyesno("Confirmar eliminación",
                                   f"¿Eliminar este {etiqueta}?\n\nEsta acción es irreversible."):
            return
        try:
            modelo = Ingrediente if kind == "ingrediente" else Producto
            with Session(engine) as s:
                obj = s.get(modelo, id_)
                if obj:
                    s.delete(obj)
                    s.commit()
            messagebox.showinfo("✅ Eliminado", f"{etiqueta} eliminado correctamente.")
            self._seleccion_actual = None
            self._poblar_arbol(self._e_buscar_arbol.get())
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # VISTAS DE DETALLE (solo lectura, con accesos a Editar / Tabla Nutricional)
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_detalle_ingrediente(self, ing_id):
        self.limpiar_pantalla()
        with Session(engine) as s:
            ing = s.get(Ingrediente, ing_id)
            if ing is None:
                messagebox.showerror("Error", "Ingrediente no encontrado.")
                self.mostrar_menu_principal()
                return

            cab = tk.Frame(self.container, bg=COLOR_BG)
            cab.pack(fill="x", padx=15, pady=(14, 2))
            tk.Label(cab, text=ing.nombre, font=FONT_TITULO, bg=COLOR_BG).pack(side="left")
            botones = tk.Frame(cab, bg=COLOR_BG)
            botones.pack(side="right")
            self._boton(botones, "✏️ Editar",
                        lambda: self.mostrar_formulario("modificar", ing_id=ing.id),
                        color_bg=COLOR_ACENTO, color_fg="white", ancho=12).pack(side="right")
            self._boton(botones, "📋 Clonar",
                        lambda: self.mostrar_formulario("crear_desde_existente", ing_id=ing.id),
                        ancho=12).pack(side="right", padx=(0, 6))
            tk.Label(self.container, text=f"Fabricante: {ing.fabricante}",
                    font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=15)

            self._separador(self.container)
            notebook = ttk.Notebook(self.container)
            notebook.pack(fill="both", expand=True, padx=10, pady=(0, 6))

            # ── Pestaña 1: General y Macronutrientes ──
            tab1_outer, tab1, _ = self._crear_scroll_frame(notebook)
            notebook.add(tab1_outer, text="General y Macronutrientes")

            lf = tk.LabelFrame(tab1, text=" Información General ", bg=COLOR_BG,
                               font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf.pack(fill="x", padx=5, pady=5)
            info = [
                ("Costo por kg",        f"${ing.costo_kg:,.2f}"),
                ("Crítico",             "Sí" if ing.critico else "No"),
                ("Humedad",             f"{ing.humedad_porcentaje * 100.0:.2f}%"),
                ("Vida útil",           f"{ing.semanas_caducidad} semanas"
                                        if ing.semanas_caducidad is not None else "—"),
                ("Ingreso de ficha",    str(ing.fecha_ingreso_ficha or "—")),
                ("Ficha técnica (PDF)", ing.ruta_pdf_ficha or "—"),
            ]
            for etiqueta, valor in info:
                fila = tk.Frame(lf, bg=COLOR_BG)
                fila.pack(fill="x", padx=8, pady=2)
                tk.Label(fila, text=f"{etiqueta}:", font=FONT_NORMAL, bg=COLOR_BG,
                        width=20, anchor="w").pack(side="left")
                tk.Label(fila, text=valor, font=FONT_NORMAL, bg=COLOR_BG,
                        anchor="w").pack(side="left")

            lf2 = tk.LabelFrame(tab1, text=" Tabla Nutricional Base (por 100 g) ",
                               bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf2.pack(fill="x", padx=5, pady=5)
            tree_nut = ttk.Treeview(lf2, columns=("nut", "val"), show="headings",
                                    height=len(NUTRIENTES))
            tree_nut.heading("nut", text="Nutriente")
            tree_nut.heading("val", text="Por 100 g")
            tree_nut.column("nut", width=320)
            tree_nut.column("val", width=120, anchor="center")
            tree_nut.pack(fill="x", padx=8, pady=8)
            for key in NUTRIENTES:
                tree_nut.insert("", "end", values=(
                    ETIQUETAS_NUTRIENTES.get(key, key),
                    redondear_minsal(getattr(ing, key, 0.0))))

            # ── Pestaña 2: Micronutrientes declarados ──
            tab2_outer, tab2, _ = self._crear_scroll_frame(notebook)
            notebook.add(tab2_outer, text="Micronutrientes")
            declarados = sorted(
                (im for im in ing.micronutrientes if im.cantidad_100g > 0),
                key=lambda im: im.micronutriente.nombre)
            if not declarados:
                tk.Label(tab2, text="— No hay micronutrientes declarados —",
                        font=FONT_NORMAL, bg=COLOR_BG, fg="#757575").pack(
                            anchor="w", padx=8, pady=10)
            else:
                tree_mic = ttk.Treeview(tab2, columns=("nombre", "cant", "unidad", "ddr"),
                                        show="headings", height=len(declarados))
                tree_mic.heading("nombre", text="Micronutriente")
                tree_mic.heading("cant", text="Por 100 g")
                tree_mic.heading("unidad", text="Unidad")
                tree_mic.heading("ddr", text="% DDR / 100 g")
                tree_mic.column("nombre", width=260)
                tree_mic.column("cant", width=110, anchor="center")
                tree_mic.column("unidad", width=90, anchor="center")
                tree_mic.column("ddr", width=120, anchor="center")
                tree_mic.pack(fill="x", padx=8, pady=8)
                for im in declarados:
                    micro = im.micronutriente
                    pct_ddr = (im.cantidad_100g / micro.ddr * 100.0) if micro.ddr else 0.0
                    tree_mic.insert("", "end", values=(
                        micro.nombre, redondear_minsal(im.cantidad_100g),
                        micro.unidad, f"{pct_ddr:.1f}%"))

            # ── Pestaña 3: Alérgenos, Aditivos y Requerimientos ──
            tab3_outer, tab3, _ = self._crear_scroll_frame(notebook)
            notebook.add(tab3_outer, text="Alérgenos, Aditivos y Requerimientos")

            lf3 = tk.LabelFrame(tab3,
                                text=" Alérgenos, Colorantes, Edulcorantes y Polialcoholes ",
                                bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf3.pack(fill="x", padx=5, pady=5)
            codigos = ing.declarables or []
            if not codigos:
                tk.Label(lf3, text="— No declara ninguno —", font=FONT_NORMAL,
                        bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=8, pady=4)
            else:
                colores_tipo = {TIPO_ALERGENO: "#C62828", TIPO_COLORANTE: "#AD1457",
                               TIPO_EDULCORANTE: "#6A1B9A", TIPO_POLIALCOHOL: "#EF6C00"}
                for codigo in codigos:
                    nombre, tipo = DECLARABLES.get(codigo, (codigo, TIPO_ALERGENO))
                    sin = SIN_CODES.get(codigo)
                    texto = f"• {nombre}" + (f" (SIN {sin})" if sin else "")
                    color = "#B71C1C" if codigo in CODIGOS_FENILALANINA else colores_tipo.get(tipo, COLOR_TEXTO)
                    if codigo in CODIGOS_FENILALANINA:
                        texto += "  ⚠ activa: FENILCETONÚRICOS: CONTIENE FENILALANINA"
                    tk.Label(lf3, text=texto, font=FONT_NORMAL, bg=COLOR_BG,
                            fg=color).pack(anchor="w", padx=8)
            if ing.cafeina_taurina:
                tk.Label(lf3, text="• Cafeína añadida / Taurina", font=FONT_NORMAL,
                        bg=COLOR_BG, fg="#B71C1C").pack(anchor="w", padx=8, pady=(4, 0))
            if ing.trazas:
                tk.Label(lf3, text=f"⚠️ Trazas: {ing.trazas}", font=FONT_NORMAL,
                        bg=COLOR_BG, fg="#555555", wraplength=640,
                        justify="left").pack(anchor="w", padx=8, pady=(6, 4))

            lf4 = tk.LabelFrame(tab3, text=" Requerimientos Alimentarios ", bg=COLOR_BG,
                               font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf4.pack(fill="x", padx=5, pady=5)
            cumplidos = [etq for campo, etq in REQUERIMIENTOS.items()
                        if getattr(ing, campo, False)]
            no_cumplidos = [etq for campo, etq in REQUERIMIENTOS.items()
                           if not getattr(ing, campo, False)]
            fila_badges = tk.Frame(lf4, bg=COLOR_BG)
            fila_badges.pack(fill="x", padx=8, pady=(8, 2))
            if cumplidos:
                for etq in cumplidos:
                    tk.Label(fila_badges, text=f" ✓ {etq} ", font=FONT_BOLD,
                            bg="#E8F5E9", fg="#2E7D32", relief="solid", bd=1,
                            padx=6, pady=3).pack(side="left", padx=3, pady=2)
            else:
                tk.Label(fila_badges, text="— No cumple ningún requerimiento —",
                        font=FONT_NORMAL, bg=COLOR_BG, fg="#757575").pack(anchor="w")
            if no_cumplidos:
                tk.Label(lf4, text="No cumple: " + ", ".join(no_cumplidos),
                        font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#9E9E9E").pack(
                            anchor="w", padx=8, pady=(2, 8))

            self._boton(self.container, "← Volver al Explorador", self.mostrar_menu_principal,
                        ancho=28).pack(pady=10)

    def mostrar_detalle_producto(self, prod_id):
        self.limpiar_pantalla()
        with Session(engine) as s:
            p = s.get(Producto, prod_id, options=self._selectinload_completo())
            if p is None:
                messagebox.showerror("Error", "Producto no encontrado.")
                self.mostrar_menu_principal()
                return

            cab = tk.Frame(self.container, bg=COLOR_BG)
            cab.pack(fill="x", padx=15, pady=(14, 2))
            tk.Label(cab, text=p.nombre, font=FONT_TITULO, bg=COLOR_BG).pack(side="left")
            botones = tk.Frame(cab, bg=COLOR_BG)
            botones.pack(side="right")
            self._boton(botones, "📊 Ver Tabla Nutricional",
                        lambda: self._ver_tabla_prod(p.id),
                        color_bg=COLOR_ACENTO, color_fg="white", ancho=22).pack(side="right")
            self._boton(botones, "✏️ Editar Producto",
                        lambda: self.mostrar_formulario_producto("editar", p.id),
                        ancho=16).pack(side="right", padx=(0, 6))

            badge_txt = ("✅ Vendible (Producto Terminado)" if p.es_vendible
                        else "🔧 Uso Interno / Preparación")
            tk.Label(self.container, text=badge_txt, font=FONT_BOLD, bg=COLOR_BG,
                    fg="#43A047" if p.es_vendible else "#EF6C00").pack(anchor="w", padx=15)
            if p.descripcion:
                tk.Label(self.container, text=p.descripcion, font=FONT_PEQUEÑA, bg=COLOR_BG,
                        fg="#757575", wraplength=640,
                        justify="left").pack(anchor="w", padx=15, pady=(2, 0))

            self._separador(self.container)
            outer, cuerpo, _ = self._crear_scroll_frame(self.container)
            outer.pack(fill="both", expand=True, padx=10)

            lf = tk.LabelFrame(cuerpo, text=" Información General ", bg=COLOR_BG,
                               font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf.pack(fill="x", padx=5, pady=5)
            vida_util = p.semanas_caducidad_efectiva()
            info = [
                ("Crítico",            "Sí" if p.critico else "No"),
                ("Humedad final",      f"{p.humedad_final * 100:.2f}%"),
                ("Porción",            f"{p.porcion_g:g} g"),
                ("Gramaje empaque",    f"{p.gramaje_g:g} g"),
                ("Vida útil efectiva", f"{vida_util} semanas" if vida_util is not None else "—"),
            ]
            for etiqueta, valor in info:
                fila = tk.Frame(lf, bg=COLOR_BG)
                fila.pack(fill="x", padx=8, pady=2)
                tk.Label(fila, text=f"{etiqueta}:", font=FONT_NORMAL, bg=COLOR_BG,
                        width=20, anchor="w").pack(side="left")
                tk.Label(fila, text=valor, font=FONT_NORMAL, bg=COLOR_BG,
                        anchor="w").pack(side="left")

            lf2 = tk.LabelFrame(cuerpo, text=" Receta Directa (un nivel) ", bg=COLOR_BG,
                               font=FONT_NORMAL, fg=COLOR_TEXTO)
            lf2.pack(fill="x", padx=5, pady=5)
            filas_r = sorted(
                [("Ingrediente", r.ingrediente.nombre, r.proporcion * 100.0)
                 for r in p.receta_ingredientes]
                + [("Producto", c.hijo.nombre, c.proporcion * 100.0)
                   for c in p.receta_productos],
                key=lambda t: -t[2])
            tree_r = ttk.Treeview(lf2, columns=("tipo", "nombre", "pct"), show="headings",
                                  height=max(len(filas_r), 1))
            tree_r.heading("tipo", text="Tipo")
            tree_r.heading("nombre", text="Componente")
            tree_r.heading("pct", text="%")
            tree_r.column("tipo", width=100, anchor="center")
            tree_r.column("nombre", width=330)
            tree_r.column("pct", width=90, anchor="center")
            tree_r.pack(fill="x", padx=8, pady=8)
            if not filas_r:
                tree_r.insert("", "end", values=("—", "Sin componentes", ""))
            for tipo, nombre, pct in filas_r:
                tree_r.insert("", "end", values=(tipo, nombre, f"{pct:.3f}"))

            self._boton(cuerpo, "← Volver al Explorador", self.mostrar_menu_principal,
                        ancho=28).pack(pady=12)

    def mostrar_formulario(self, modo, ing_id=None):
        self.limpiar_pantalla()
        self._critico_var = tk.BooleanVar(value=False)
        self._cafeina_var = tk.BooleanVar(value=False)
        titulos = {
            "crear_nuevo":           "Nuevo Ingrediente",
            "crear_desde_existente": "Clonar Ingrediente",
            "modificar":             "Modificar Ingrediente",
        }
        self._titulo(self.container, titulos[modo])

        if modo in ("crear_desde_existente", "modificar"):
            fb = tk.Frame(self.container, bg=COLOR_BG)
            fb.pack(fill="x", padx=20, pady=(0, 6))
            tk.Label(fb, text="🔍  Buscar ingrediente existente:",
                     font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
            self.combo_busqueda = self._crear_combobox_buscable(
                fb, self.cargar_datos_en_formulario)
            self.combo_busqueda.pack(fill="x", pady=4)

        # Al crear/clonar vuelve al explorador; al modificar vuelve al
        # detalle de este ingrediente — edición in-place, no a un listado.
        destino = (self.mostrar_menu_principal if ing_id is None
                   else lambda: self.mostrar_detalle_ingrediente(ing_id))
        self._barra_botones(destino, lambda: self.guardar_ingrediente(modo),
                            "💾  Guardar Ingrediente")
        self._separador(self.container)

        # 3 pestañas — ttk.Notebook crea los tres frames de una sola vez y
        # solo cambia cuál se muestra, así que el estado de las otras dos no
        # se pierde al navegar entre ellas (no hay que guardarlo a mano).
        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # ── Pestaña 1: General y Macronutrientes ──
        tab1_outer, tab1, _ = self._crear_scroll_frame(notebook)
        notebook.add(tab1_outer, text="General y Macronutrientes")

        row_crit = tk.Frame(tab1, bg=COLOR_BG)
        row_crit.pack(fill="x", pady=6, padx=4)
        tk.Checkbutton(row_crit, text="  Crítico",
                       variable=self._critico_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")
        tk.Label(row_crit, text="(ingrediente aporta azúcar/sodio/grasa añadida)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(side="left", padx=8)

        for key, (label_text, _) in self.campos_formulario.items():
            row = tk.Frame(tab1, bg=COLOR_BG)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=label_text, font=FONT_NORMAL, bg=COLOR_BG,
                     fg=COLOR_TEXTO, width=26, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            entry.pack(side="right", expand=True, fill="x")
            self.entries[key] = entry

        # Trazabilidad: fecha de ingreso de la ficha, PDF y vida útil
        self._separador(tab1)
        tk.Label(tab1, text="Trazabilidad", font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4)

        row_fv = tk.Frame(tab1, bg=COLOR_BG)
        row_fv.pack(fill="x", pady=3, padx=4)
        tk.Label(row_fv, text="Ingreso ficha (AAAA-MM-DD):", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_fecha_ingreso = tk.Entry(row_fv, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_fecha_ingreso.pack(side="right", expand=True, fill="x")

        row_pdf = tk.Frame(tab1, bg=COLOR_BG)
        row_pdf.pack(fill="x", pady=3, padx=4)
        tk.Label(row_pdf, text="Ficha técnica (PDF):", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_pdf_path = tk.Entry(row_pdf, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_pdf_path.pack(side="left", expand=True, fill="x")
        self._boton(row_pdf, "📂", lambda: self._seleccionar_pdf(),
                    ancho=4).pack(side="right", padx=4)

        row_mc = tk.Frame(tab1, bg=COLOR_BG)
        row_mc.pack(fill="x", pady=3, padx=4)
        tk.Label(row_mc, text="Vida útil (semanas):", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_meses_cad = tk.Entry(row_mc, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_meses_cad.pack(side="right", expand=True, fill="x")

        # ── Pestaña 2: Micronutrientes (vitaminas y minerales) ──
        tab2_outer, tab2, _ = self._crear_scroll_frame(notebook)
        notebook.add(tab2_outer, text="Micronutrientes")
        self._construir_seccion_micronutrientes(tab2)

        # ── Pestaña 3: Alérgenos, Aditivos y Requerimientos ──
        tab3_outer, tab3, _ = self._crear_scroll_frame(notebook)
        notebook.add(tab3_outer, text="Alérgenos, Aditivos y Requerimientos")
        self._construir_seccion_etiquetado(tab3)

        # Llegó desde la vista de detalle con un ingrediente puntual (editar
        # o clonar desde él): precarga sus datos sin obligar a buscarlo de
        # nuevo en el combo.
        if modo in ("modificar", "crear_desde_existente") and ing_id is not None:
            id_unico = next((k for k, v in self.mapa_ingredientes.items() if v == ing_id), None)
            if id_unico:
                self.combo_busqueda.set(id_unico)
            self.cargar_datos_en_formulario(ing_id=ing_id)

    def _grid_declarables(self, parent, tipo, color=None):
        """Grilla de checkboxes para una categoría del catálogo DECLARABLES."""
        grid = tk.Frame(parent, bg=COLOR_BG)
        grid.pack(fill="x", padx=4, pady=(0, 6))
        items = [(c, n) for c, (n, t) in DECLARABLES.items() if t == tipo]
        for i, (codigo, nombre) in enumerate(items):
            var = tk.BooleanVar(value=False)
            self._declarable_vars[codigo] = var
            sin = SIN_CODES.get(codigo)
            texto = f"  {nombre} (SIN {sin})" if sin else f"  {nombre}"
            # Aspartamo y su sal con acesulfamo disparan la leyenda de
            # fenilcetonúricos — se marca en el propio checkbox, no solo en
            # el aviso general de la categoría, para que no pase inadvertido.
            if codigo in CODIGOS_FENILALANINA:
                texto += "  ⚠ activa: Fenilalanina"
            tk.Checkbutton(grid, text=texto, variable=var,
                           font=FONT_NORMAL,
                           bg=COLOR_BG, fg=("#B71C1C" if codigo in CODIGOS_FENILALANINA
                                           else (color or COLOR_TEXTO)),
                           selectcolor="#FFFFFF", activebackground=COLOR_BG,
                           anchor="w").grid(row=i // 2, column=i % 2,
                                            sticky="w", padx=4)

    def _construir_seccion_etiquetado(self, frame_form):
        """
        Catálogos oficiales RSA (D.S. 977/1996) y Res. Ex. 427/2010 que el
        producto final hereda del árbol: alérgenos, colorantes destacados,
        edulcorantes no nutritivos y polialcoholes (unión), cafeína/taurina y
        trazas (propagación), requerimientos alimentarios (intersección).
        """
        tk.Label(frame_form, text="A. Alérgenos Oficiales (Res. Ex. 427/2010, Art. 107 h)",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4)
        tk.Label(frame_form,
                 text="Marcar solo lo que la ficha técnica declara como presente.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=4, pady=(0, 2))
        self._grid_declarables(frame_form, TIPO_ALERGENO)

        tk.Label(frame_form, text="B. Colorantes de Rotulación Destacada (Art. 136)",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4, pady=(4, 0))
        tk.Label(frame_form, text="Exigen negrilla en la lista de ingredientes.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=4, pady=(0, 2))
        self._grid_declarables(frame_form, TIPO_COLORANTE, color="#C62828")

        tk.Label(frame_form, text="C. Edulcorantes No Nutritivos (Art. 146)",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4, pady=(4, 0))
        tk.Label(frame_form,
                 text=("Exigen MAYÚSCULAS y negrilla. El aspartamo y su sal con "
                       "acesulfamo agregan la leyenda de fenilcetonúricos."),
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575",
                 justify="left").pack(anchor="w", padx=4, pady=(0, 2))
        self._grid_declarables(frame_form, TIPO_EDULCORANTE, color="#AD1457")

        tk.Label(frame_form, text="D. Polialcoholes / Polioles (Art. 151)",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4, pady=(4, 0))
        tk.Label(frame_form,
                 text="Cualquiera de estos agrega la advertencia de efecto laxante.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=4, pady=(0, 2))
        self._grid_declarables(frame_form, TIPO_POLIALCOHOL, color="#EF6C00")

        tk.Label(frame_form, text="E. Otros Compuestos con Advertencia y Trazas",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4, pady=(4, 0))
        tk.Checkbutton(frame_form, text="  Cafeína añadida / Taurina (bebidas energéticas)",
                       variable=self._cafeina_var,
                       font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG,
                       anchor="w").pack(anchor="w", padx=4, pady=(2, 4))

        row_tz = tk.Frame(frame_form, bg=COLOR_BG)
        row_tz.pack(fill="x", pady=(0, 3), padx=4)
        tk.Label(row_tz, text="Trazas / contaminación:", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_trazas = tk.Entry(row_tz, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_trazas.pack(side="right", expand=True, fill="x")
        tk.Label(frame_form, text='Frase tal como se imprimirá. Ej: "Puede contener maní."',
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=4)

        tk.Label(frame_form, text="Requerimientos alimentarios",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4, pady=(10, 0))
        tk.Label(frame_form,
                 text="El producto final los hereda solo si TODAS sus materias primas los cumplen.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(anchor="w", padx=4)

        grid_req = tk.Frame(frame_form, bg=COLOR_BG)
        grid_req.pack(fill="x", padx=4, pady=(2, 0))
        for i, (campo, etiqueta) in enumerate(REQUERIMIENTOS.items()):
            var = tk.BooleanVar(value=False)
            self._req_vars[campo] = var
            tk.Checkbutton(grid_req, text=f"  {etiqueta}", variable=var,
                           font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_TEXTO,
                           selectcolor="#FFFFFF", activebackground=COLOR_BG,
                           anchor="w").grid(row=i // 2, column=i % 2,
                                            sticky="w", padx=4)

    def _construir_seccion_micronutrientes(self, frame_form):
        """
        Campos de micronutrientes del ingrediente, uno por entrada del catálogo.

        Se dejan en blanco los que la ficha técnica del proveedor no declara;
        solo se guardan los que tengan un valor mayor a cero.
        """
        tk.Label(frame_form, text="Micronutrientes (por 100 g)",
                 font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4)
        tk.Label(frame_form,
                 text=("Se declaran en la tabla nutricional solo si aportan ≥5% "
                       "de la DDR por porción (RSA Art 118).\n"
                       "Deja en blanco los que la ficha técnica no informe."),
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575",
                 justify="left").pack(anchor="w", padx=4, pady=(0, 4))

        with Session(engine) as s:
            catalogo = [
                {"id": m.id, "nombre": m.nombre, "unidad": m.unidad, "ddr": m.ddr}
                for m in s.query(Micronutriente).order_by(Micronutriente.id).all()
            ]

        if not catalogo:
            tk.Label(frame_form,
                     text=("⚠️  El catálogo de micronutrientes está vacío. "
                           "Ejecuta scripts/seed_welliz_canela.py para cargarlo."),
                     font=FONT_PEQUEÑA, bg=COLOR_BG, fg=COLOR_WARN,
                     justify="left").pack(anchor="w", padx=4, pady=4)
            return

        for m in catalogo:
            row = tk.Frame(frame_form, bg=COLOR_BG)
            row.pack(fill="x", pady=2, padx=4)
            tk.Label(row, text=f"{m['nombre']} ({m['unidad']})",
                     font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_TEXTO,
                     width=26, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            entry.pack(side="left", expand=True, fill="x")
            tk.Label(row, text=f"DDR {m['ddr']:g} {m['unidad']}",
                     font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#9E9E9E",
                     width=16, anchor="e").pack(side="right", padx=(6, 0))
            self._entries_micro[m["id"]] = entry
            self._nombres_micro[m["id"]] = m["nombre"]

    def _seleccionar_pdf(self):
        path = filedialog.askopenfilename(
            title="Seleccionar ficha técnica PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
            initialdir="data/fichas_tecnicas")
        if path:
            self._e_pdf_path.delete(0, tk.END)
            self._e_pdf_path.insert(0, path)
            if not self._e_fecha_ingreso.get().strip():
                import os
                from datetime import date
                st = os.stat(path)
                ts = getattr(st, "st_birthtime", st.st_mtime)
                self._e_fecha_ingreso.insert(0, str(date.fromtimestamp(ts)))

    def cargar_datos_en_formulario(self, event=None, ing_id=None):
        if ing_id is None:
            seleccion = self.combo_busqueda.get()
            if not seleccion or seleccion not in self.mapa_ingredientes:
                return
            ing_id = self.mapa_ingredientes[seleccion]
        self.ingrediente_actual_id = ing_id
        with Session(engine) as s:
            ing = s.get(Ingrediente, self.ingrediente_actual_id)
            if ing is None:
                return
            self._critico_var.set(ing.critico)
            for key, entry in self.entries.items():
                valor = getattr(ing, key)
                if key in self._campos_en_fraccion:
                    valor = round(valor * 100.0, 6)
                entry.delete(0, tk.END)
                entry.insert(0, str(valor))
            # Trazabilidad
            self._e_fecha_ingreso.delete(0, tk.END)
            if ing.fecha_ingreso_ficha:
                self._e_fecha_ingreso.insert(0, str(ing.fecha_ingreso_ficha))
            self._e_pdf_path.delete(0, tk.END)
            if ing.ruta_pdf_ficha:
                self._e_pdf_path.insert(0, ing.ruta_pdf_ficha)
            self._e_meses_cad.delete(0, tk.END)
            if ing.semanas_caducidad is not None:
                self._e_meses_cad.insert(0, str(ing.semanas_caducidad))
            # Etiquetado
            codigos_decl = set(ing.declarables or [])
            for codigo, var in self._declarable_vars.items():
                var.set(codigo in codigos_decl)
            self._cafeina_var.set(bool(ing.cafeina_taurina))
            for campo, var in self._req_vars.items():
                var.set(bool(getattr(ing, campo, False)))
            self._e_trazas.delete(0, tk.END)
            if ing.trazas:
                self._e_trazas.insert(0, ing.trazas)
            # Micronutrientes nativos: queda en blanco lo que el ingrediente no declara
            declarados = {im.micronutriente_id: im.cantidad_100g
                          for im in ing.micronutrientes}
            for mid, entry in self._entries_micro.items():
                entry.delete(0, tk.END)
                cantidad = declarados.get(mid)
                if cantidad:
                    entry.insert(0, f"{cantidad:g}")

    def _leer_micronutrientes_formulario(self) -> dict[int, float]:
        """
        Lee los campos de micronutrientes del formulario de ingredientes.

        Un campo en blanco no genera fila: que la ficha tecnica no informe un
        micronutriente no es lo mismo que declarar que vale cero. Por eso el
        cero tambien se descarta, en vez de guardarse como aporte nulo.
        """
        valores: dict[int, float] = {}
        for mid, entry in self._entries_micro.items():
            texto = entry.get().strip().replace(",", ".")
            if not texto:
                continue
            nombre = self._nombres_micro.get(mid, f"micronutriente {mid}")
            try:
                cantidad = float(texto)
            except ValueError:
                raise ValueError(f"El valor de '{nombre}' no es un numero valido.")
            if cantidad < 0:
                raise ValueError(f"El valor de '{nombre}' no puede ser negativo.")
            if cantidad > 0:
                valores[mid] = cantidad
        return valores

    def _sincronizar_micronutrientes(self, ing, micros: dict[int, float]):
        """
        Deja ingrediente_micronutriente igual a lo que muestra el formulario:
        actualiza las cantidades que cambiaron, agrega las nuevas y quita las
        que el usuario borro (delete-orphan emite el DELETE).
        """
        existentes = {im.micronutriente_id: im for im in ing.micronutrientes}
        for mid, cantidad in micros.items():
            if mid in existentes:
                existentes[mid].cantidad_100g = cantidad
            else:
                ing.micronutrientes.append(
                    IngredienteMicronutriente(micronutriente_id=mid,
                                              cantidad_100g=cantidad))
        for mid, im in existentes.items():
            if mid not in micros:
                ing.micronutrientes.remove(im)

    def guardar_ingrediente(self, modo):
        try:
            datos = {}
            for key, (label_text, tipo_dato) in self.campos_formulario.items():
                valor_str = self.entries[key].get().strip()
                if not valor_str:
                    if tipo_dato is str:
                        raise ValueError(f"El campo '{label_text}' no puede estar vacío.")
                    valor_str = "0.0"
                if tipo_dato is float:
                    valor_str = valor_str.replace(",", ".")
                valor = tipo_dato(valor_str)
                if key in self._campos_en_fraccion and tipo_dato is float:
                    valor = valor / 100.0
                datos[key] = valor
            datos["critico"] = self._critico_var.get()

            # Trazabilidad
            fv_str = self._e_fecha_ingreso.get().strip()
            if fv_str:
                from datetime import date
                datos["fecha_ingreso_ficha"] = date.fromisoformat(fv_str)
            else:
                datos["fecha_ingreso_ficha"] = None
            pdf_str = self._e_pdf_path.get().strip()
            if pdf_str:
                datos["ruta_pdf_ficha"] = pdf_str
            mc_str = self._e_meses_cad.get().strip()
            datos["semanas_caducidad"] = None
            if mc_str:
                datos["semanas_caducidad"] = int(mc_str)

            # Etiquetado (lista nueva: la columna JSON no detecta mutaciones)
            datos["declarables"] = [c for c, v in self._declarable_vars.items() if v.get()]
            datos["cafeina_taurina"] = self._cafeina_var.get()
            datos["trazas"] = self._e_trazas.get().strip() or None
            for campo, var in self._req_vars.items():
                datos[campo] = var.get()

            micros = self._leer_micronutrientes_formulario()

            with Session(engine) as s:
                if modo == "modificar":
                    if not self.ingrediente_actual_id:
                        raise ValueError("Debes seleccionar un ingrediente para modificar.")
                    ing = s.get(Ingrediente, self.ingrediente_actual_id)
                    for k, v in datos.items():
                        setattr(ing, k, v)
                    self._sincronizar_micronutrientes(ing, micros)
                else:
                    ing = Ingrediente(**datos)
                    for mid, cantidad in micros.items():
                        ing.micronutrientes.append(
                            IngredienteMicronutriente(micronutriente_id=mid,
                                                      cantidad_100g=cantidad))
                    s.add(ing)
                s.commit()
                ing_id_final = ing.id

            messagebox.showinfo("✅ Éxito", "Ingrediente guardado correctamente.")
            self.mostrar_detalle_ingrediente(ing_id_final)
        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror("Duplicado", "Ya existe un ingrediente con ese nombre y fabricante.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # PRODUCTOS (nodo único del BOM: receta de ingredientes y/o productos)
    #
    # Sin menú propio: se crean/editan/eliminan/visualizan desde el árbol
    # explorador (mostrar_menu_principal) y sus vistas de detalle.
    # ══════════════════════════════════════════════════════════════════════════

    # ── Formulario crear/editar Producto (unificado) ──────────────────────────

    def mostrar_formulario_producto(self, modo, prod_id=None):
        self.limpiar_pantalla()
        self._prod_receta_ing: list[dict] = []
        self._prod_receta_prod: list[dict] = []
        self._prod_costos: list[dict] = []
        self._critico_var = tk.BooleanVar(value=False)
        self._vendible_var = tk.BooleanVar(value=True)

        titulo = "Nuevo Producto" if modo == 'crear' else "Editar Producto"
        self._titulo(self.container, titulo)

        # Al crear vuelve al explorador; al editar vuelve al detalle de este
        # producto, no al listado — es el patrón de edición in-place.
        volver = (self.mostrar_menu_principal if modo == 'crear'
                 else lambda: self.mostrar_detalle_producto(prod_id))
        self._barra_botones(volver, lambda: self._guardar_producto(modo, prod_id),
                            "💾  Guardar Producto")
        self._separador(self.container)

        outer, frame_form, _ = self._crear_scroll_frame(self.container)
        outer.pack(fill="both", expand=True, padx=10)

        # ── Sección 1: Datos generales ──
        lf1 = tk.LabelFrame(frame_form, text=" Datos Generales ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf1.pack(fill="x", padx=5, pady=5)

        self._prod_entries: dict[str, tk.Entry] = {}
        campos = [
            ("nombre",        "Nombre:"),
            ("descripcion",   "Descripción (opcional):"),
            ("humedad_final", "Humedad final (%, ej: 3.0):"),
        ]
        campos.extend([
            ("porcion_g",     "Porción (g, ej: 25):"),
            ("gramaje_g",     "Gramaje empaque (g, ej: 200):"),
        ])
        campos.append(("semanas_caducidad_override",
                       "Vida útil manual (semanas, opcional):"))
        # Trazas del proceso/línea de este nodo; suben hasta el producto final
        campos.append(("trazas", "Trazas de la línea (opcional):"))

        defaults = {"porcion_g": "25", "gramaje_g": "200"}
        for key, label in campos:
            row = tk.Frame(lf1, bg=COLOR_BG)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=label, font=FONT_NORMAL, bg=COLOR_BG,
                     width=28, anchor="w").pack(side="left")
            e = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            if key in defaults:
                e.insert(0, defaults[key])
            e.pack(side="right", expand=True, fill="x")
            self._prod_entries[key] = e

        # Checkbox Crítico con auto-detección
        row_crit = tk.Frame(lf1, bg=COLOR_BG)
        row_crit.pack(fill="x", padx=8, pady=3)
        tk.Checkbutton(row_crit, text="  Crítico",
                       variable=self._critico_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")
        self._lbl_critico_auto = tk.Label(row_crit, text="(aplica sellos de advertencia)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575")
        self._lbl_critico_auto.pack(side="left", padx=8)

        # Checkbox de clasificación comercial — no afecta la receta: un
        # Producto vendible puede seguir siendo componente de otro.
        row_vend = tk.Frame(lf1, bg=COLOR_BG)
        row_vend.pack(fill="x", padx=8, pady=3)
        tk.Checkbutton(row_vend, text="  Producto apto para venta (Producto Terminado)",
                       variable=self._vendible_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")

        # ── Sección 2: Receta de ingredientes ──
        lf2 = tk.LabelFrame(frame_form, text=" Receta de Ingredientes (% en peso) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf2.pack(fill="x", padx=5, pady=5)

        fa = tk.Frame(lf2, bg=COLOR_BG)
        fa.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa, text="Ingrediente:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_combo_ing = self._crear_combobox_buscable(fa, lambda e: None)
        self._prod_combo_ing.pack(side="left", padx=4)
        tk.Label(fa, text="%:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_e_pct_ing = tk.Entry(fa, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._prod_e_pct_ing.pack(side="left", padx=4)
        self._boton(fa, "➕", self._prod_agregar_ing,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left")

        ft = tk.Frame(lf2, bg=COLOR_BG)
        ft.pack(fill="x", padx=8, pady=2)
        self._prod_tree_receta_ing = ttk.Treeview(ft,
            columns=("ingrediente", "pct"), show="headings", height=4)
        self._prod_tree_receta_ing.heading("ingrediente", text="Ingrediente")
        self._prod_tree_receta_ing.heading("pct", text="%")
        self._prod_tree_receta_ing.column("ingrediente", width=360)
        self._prod_tree_receta_ing.column("pct", width=80, anchor="center")
        sb_i = ttk.Scrollbar(ft, orient="vertical", command=self._prod_tree_receta_ing.yview)
        self._prod_tree_receta_ing.configure(yscrollcommand=sb_i.set)
        self._prod_tree_receta_ing.pack(side="left", fill="x", expand=True)
        sb_i.pack(side="right", fill="y")

        fc = tk.Frame(lf2, bg=COLOR_BG)
        fc.pack(fill="x", padx=8, pady=(2, 8))
        self._boton(fc, "🗑️ Quitar fila", self._prod_quitar_ing,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        # ── Sección 2b: Composición de otros Productos ──
        lf2b = tk.LabelFrame(frame_form, text=" Composición de Productos (% en peso) ",
                             bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf2b.pack(fill="x", padx=5, pady=5)

        fa2 = tk.Frame(lf2b, bg=COLOR_BG)
        fa2.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa2, text="Producto:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_combo_prod = self._crear_combobox_producto(fa2, lambda e: None)
        self._prod_combo_prod.pack(side="left", padx=4)
        tk.Label(fa2, text="%:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_e_pct_prod = tk.Entry(fa2, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._prod_e_pct_prod.pack(side="left", padx=4)
        self._boton(fa2, "➕", self._prod_agregar_prod,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left")

        ft2 = tk.Frame(lf2b, bg=COLOR_BG)
        ft2.pack(fill="x", padx=8, pady=2)
        self._prod_tree_receta_prod = ttk.Treeview(ft2,
            columns=("producto", "pct"), show="headings", height=4)
        self._prod_tree_receta_prod.heading("producto", text="Producto")
        self._prod_tree_receta_prod.heading("pct", text="%")
        self._prod_tree_receta_prod.column("producto", width=360)
        self._prod_tree_receta_prod.column("pct", width=80, anchor="center")
        sb_p = ttk.Scrollbar(ft2, orient="vertical", command=self._prod_tree_receta_prod.yview)
        self._prod_tree_receta_prod.configure(yscrollcommand=sb_p.set)
        self._prod_tree_receta_prod.pack(side="left", fill="x", expand=True)
        sb_p.pack(side="right", fill="y")

        fc2 = tk.Frame(lf2b, bg=COLOR_BG)
        fc2.pack(fill="x", padx=8, pady=(2, 4))
        self._prod_lbl_total = tk.Label(fc2, text="Total: 0.00%",
                                        font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_PELIGRO)
        self._prod_lbl_total.pack(side="left")
        self._boton(fc2, "🗑️ Quitar fila", self._prod_quitar_prod,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        # ── Sección 3: Cascada de costos ──
        lf3 = tk.LabelFrame(frame_form, text=" Costos Operativos (cascada secuencial) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf3.pack(fill="x", padx=5, pady=5)

        fa3 = tk.Frame(lf3, bg=COLOR_BG)
        fa3.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa3, text="Nombre:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_e_cnombre = tk.Entry(fa3, font=FONT_NORMAL, width=14, relief="solid", bd=1)
        self._prod_e_cnombre.pack(side="left", padx=3)
        tk.Label(fa3, text="Tipo:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_cb_ctipo = ttk.Combobox(fa3, values=["porcentual", "fijo"],
                                            state="readonly", width=10, font=FONT_NORMAL)
        self._prod_cb_ctipo.set("porcentual")
        self._prod_cb_ctipo.pack(side="left", padx=3)
        tk.Label(fa3, text="Valor:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._prod_e_cvalor = tk.Entry(fa3, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._prod_e_cvalor.pack(side="left", padx=3)
        tk.Label(fa3, text="(% o $/kg)", font=FONT_PEQUEÑA, bg=COLOR_BG,
                 fg="#757575").pack(side="left", padx=2)
        self._boton(fa3, "➕", self._prod_agregar_costo,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left", padx=4)

        ft3 = tk.Frame(lf3, bg=COLOR_BG)
        ft3.pack(fill="x", padx=8, pady=2)
        self._prod_tree_costos = ttk.Treeview(ft3,
            columns=("orden", "nombre", "tipo", "valor"), show="headings", height=4)
        self._prod_tree_costos.heading("orden", text="#")
        self._prod_tree_costos.heading("nombre", text="Proceso")
        self._prod_tree_costos.heading("tipo", text="Tipo")
        self._prod_tree_costos.heading("valor", text="Valor")
        self._prod_tree_costos.column("orden", width=30, anchor="center")
        self._prod_tree_costos.column("nombre", width=200)
        self._prod_tree_costos.column("tipo", width=100, anchor="center")
        self._prod_tree_costos.column("valor", width=100, anchor="center")
        sb_c = ttk.Scrollbar(ft3, orient="vertical", command=self._prod_tree_costos.yview)
        self._prod_tree_costos.configure(yscrollcommand=sb_c.set)
        self._prod_tree_costos.pack(side="left", fill="x", expand=True)
        sb_c.pack(side="right", fill="y")

        fc3 = tk.Frame(lf3, bg=COLOR_BG)
        fc3.pack(fill="x", padx=8, pady=(2, 8))
        self._boton(fc3, "🗑️ Quitar paso", self._prod_quitar_costo,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        if modo == 'editar' and prod_id:
            self._prod_cargar_existente(prod_id)

    # ── Helpers del formulario Producto ────────────────────────────────────────

    def _prod_actualizar_total(self):
        total_ing = sum(f["pct"] for f in self._prod_receta_ing)
        total_prod = sum(f["pct"] for f in self._prod_receta_prod)
        total = total_ing + total_prod
        ok = abs(total - 100.0) < 0.01
        self._prod_lbl_total.config(
            text=f"Total: {total:.4f}% (Ing: {total_ing:.2f}% + Prod: {total_prod:.2f}%)  "
                 f"{'✅' if ok else '⚠️ debe ser 100.00%'}",
            fg=COLOR_EXITO if ok else COLOR_PELIGRO)

        # Auto-detección de crítico
        hay_critico = False
        for fila in self._prod_receta_ing:
            with Session(engine) as s:
                ing = s.get(Ingrediente, fila["ing_id"])
                if ing and ing.critico:
                    hay_critico = True
                    break
        if not hay_critico:
            for fila in self._prod_receta_prod:
                with Session(engine) as s:
                    p = s.get(Producto, fila["prod_id"], options=self._selectinload_completo())
                    if p and p.critico_calculado():
                        hay_critico = True
                        break
        if hay_critico and not self._critico_var.get():
            self._lbl_critico_auto.config(
                text="⚠️ Auto-detección: ingrediente crítico encontrado",
                fg=COLOR_WARN)
        elif not hay_critico and self._critico_var.get():
            self._lbl_critico_auto.config(
                text="ℹ️ Ningún ingrediente crítico detectado (forzado manual)",
                fg="#757575")
        else:
            self._lbl_critico_auto.config(
                text="(aplica sellos de advertencia)", fg="#757575")

    def _prod_refrescar_tree_receta_ing(self):
        for item in self._prod_tree_receta_ing.get_children():
            self._prod_tree_receta_ing.delete(item)
        for fila in self._prod_receta_ing:
            self._prod_tree_receta_ing.insert("", "end",
                values=(fila["nombre"], f"{fila['pct']:.4f}"))
        self._prod_actualizar_total()

    def _prod_refrescar_tree_receta_prod(self):
        for item in self._prod_tree_receta_prod.get_children():
            self._prod_tree_receta_prod.delete(item)
        for fila in self._prod_receta_prod:
            self._prod_tree_receta_prod.insert("", "end",
                values=(fila["nombre"], f"{fila['pct']:.4f}"))
        self._prod_actualizar_total()

    def _prod_agregar_ing(self):
        nombre = self._prod_combo_ing.get().strip()
        pct_str = self._prod_e_pct_ing.get().strip().replace(",", ".")
        if not nombre or nombre not in self.mapa_ingredientes:
            messagebox.showerror("Error", "Selecciona un ingrediente válido de la lista.")
            return
        try:
            pct = float(pct_str)
            if pct <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingresa un porcentaje válido (número > 0).")
            return
        for fila in self._prod_receta_ing:
            if fila["ing_id"] == self.mapa_ingredientes[nombre]:
                fila["pct"] = pct
                self._prod_refrescar_tree_receta_ing()
                self._prod_e_pct_ing.delete(0, tk.END)
                return
        self._prod_receta_ing.append({"ing_id": self.mapa_ingredientes[nombre],
                                       "nombre": nombre, "pct": pct})
        self._prod_refrescar_tree_receta_ing()
        self._prod_combo_ing.set("")
        self._prod_e_pct_ing.delete(0, tk.END)

    def _prod_quitar_ing(self):
        sel = self._prod_tree_receta_ing.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona una fila para quitar.")
            return
        nombre = self._prod_tree_receta_ing.item(sel[0])["values"][0]
        self._prod_receta_ing = [f for f in self._prod_receta_ing if f["nombre"] != nombre]
        self._prod_refrescar_tree_receta_ing()

    def _prod_agregar_prod(self):
        nombre = self._prod_combo_prod.get().strip()
        pct_str = self._prod_e_pct_prod.get().strip().replace(",", ".")
        if not nombre or nombre not in self.mapa_productos:
            messagebox.showerror("Error", "Selecciona un Producto válido de la lista.")
            return
        try:
            pct = float(pct_str)
            if pct <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingresa un porcentaje válido (número > 0).")
            return
        for fila in self._prod_receta_prod:
            if fila["prod_id"] == self.mapa_productos[nombre]:
                fila["pct"] = pct
                self._prod_refrescar_tree_receta_prod()
                self._prod_e_pct_prod.delete(0, tk.END)
                return
        self._prod_receta_prod.append({"prod_id": self.mapa_productos[nombre],
                                        "nombre": nombre, "pct": pct})
        self._prod_refrescar_tree_receta_prod()
        self._prod_combo_prod.set("")
        self._prod_e_pct_prod.delete(0, tk.END)

    def _prod_quitar_prod(self):
        sel = self._prod_tree_receta_prod.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona una fila para quitar.")
            return
        nombre = self._prod_tree_receta_prod.item(sel[0])["values"][0]
        self._prod_receta_prod = [f for f in self._prod_receta_prod if f["nombre"] != nombre]
        self._prod_refrescar_tree_receta_prod()

    def _prod_refrescar_tree_costos(self):
        for item in self._prod_tree_costos.get_children():
            self._prod_tree_costos.delete(item)
        for i, fila in enumerate(self._prod_costos, 1):
            vd = (f"{fila['valor']:.4f}%" if fila["tipo"] == "porcentual"
                  else f"${fila['valor']:,.2f}")
            self._prod_tree_costos.insert("", "end",
                values=(i, fila["nombre"], fila["tipo"], vd))

    def _prod_agregar_costo(self):
        nombre = self._prod_e_cnombre.get().strip()
        tipo = self._prod_cb_ctipo.get()
        valor_str = self._prod_e_cvalor.get().strip().replace(",", ".")
        if not nombre:
            messagebox.showerror("Error", "Ingresa un nombre para el proceso.")
            return
        try:
            valor = float(valor_str)
            if valor < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingresa un valor numérico válido (>= 0).")
            return
        self._prod_costos.append({"nombre": nombre, "tipo": tipo, "valor": valor})
        self._prod_refrescar_tree_costos()
        self._prod_e_cnombre.delete(0, tk.END)
        self._prod_e_cvalor.delete(0, tk.END)

    def _prod_quitar_costo(self):
        sel = self._prod_tree_costos.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona un paso para quitar.")
            return
        orden = int(self._prod_tree_costos.item(sel[0])["values"][0]) - 1
        self._prod_costos.pop(orden)
        self._prod_refrescar_tree_costos()

    def _prod_cargar_existente(self, prod_id):
        with Session(engine) as s:
            p = s.get(Producto, prod_id, options=self._selectinload_completo())
            if p is None:
                return
            self._prod_entries["nombre"].insert(0, p.nombre)
            self._prod_entries["descripcion"].insert(0, p.descripcion or "")
            self._prod_entries["humedad_final"].insert(0, str(round(p.humedad_final * 100.0, 6)))
            self._critico_var.set(p.critico)
            self._vendible_var.set(p.es_vendible)
            for campo in ("porcion_g", "gramaje_g"):
                self._prod_entries[campo].delete(0, tk.END)
                self._prod_entries[campo].insert(0, str(getattr(p, campo)))
            self._prod_entries["semanas_caducidad_override"].delete(0, tk.END)
            if p.semanas_caducidad_override is not None:
                self._prod_entries["semanas_caducidad_override"].insert(
                    0, str(p.semanas_caducidad_override))
            self._prod_entries["trazas"].delete(0, tk.END)
            if p.trazas:
                self._prod_entries["trazas"].insert(0, p.trazas)
            for rel in p.receta_ingredientes:
                self._prod_receta_ing.append({
                    "ing_id": rel.ingrediente_id,
                    "nombre": rel.ingrediente.id_unico,
                    "pct":    round(rel.proporcion * 100.0, 6),
                })
            for comp in p.receta_productos:
                self._prod_receta_prod.append({
                    "prod_id": comp.hijo_id,
                    "nombre":  comp.hijo.nombre,
                    "pct":     round(comp.proporcion * 100.0, 6),
                })
            for co in p.costos_operativos:
                self._prod_costos.append({
                    "nombre": co.nombre,
                    "tipo":   co.tipo,
                    "valor":  round(co.valor * 100.0, 6) if co.tipo == "porcentual" else co.valor,
                })
        self._prod_refrescar_tree_receta_ing()
        self._prod_refrescar_tree_receta_prod()
        self._prod_refrescar_tree_costos()

    def _guardar_producto(self, modo, prod_id):
        try:
            nombre = self._prod_entries["nombre"].get().strip()
            desc = self._prod_entries["descripcion"].get().strip()
            h_str = self._prod_entries["humedad_final"].get().strip().replace(",", ".")
            critico = self._critico_var.get()
            vendible = self._vendible_var.get()

            if not nombre:
                raise ValueError("El nombre del Producto no puede estar vacío.")
            if not self._prod_receta_ing and not self._prod_receta_prod:
                raise ValueError("Agrega al menos un ingrediente o producto a la receta.")

            humedad_f = float(h_str) / 100.0 if h_str else 0.0
            total_pct = (sum(f["pct"] for f in self._prod_receta_ing)
                        + sum(f["pct"] for f in self._prod_receta_prod))
            if abs(total_pct - 100.0) > 0.01:
                raise ValueError(
                    f"Los porcentajes deben sumar 100%.\nTotal actual: {total_pct:.4f}%")

            porcion_g = 25.0
            gramaje_g = 200.0
            semanas_ov = None
            sv = self._prod_entries["semanas_caducidad_override"].get().strip()
            if sv:
                semanas_ov = int(sv)
            trazas = self._prod_entries["trazas"].get().strip() or None
            porcion_g = float(
                self._prod_entries["porcion_g"].get().strip().replace(",", ".") or "25")
            gramaje_g = float(
                self._prod_entries["gramaje_g"].get().strip().replace(",", ".") or "200")

            with Session(engine) as s:
                if modo == "crear":
                    p = Producto(nombre=nombre, descripcion=desc,
                                humedad_final=humedad_f, critico=critico,
                                es_vendible=vendible,
                                porcion_g=porcion_g, gramaje_g=gramaje_g,
                                semanas_caducidad_override=semanas_ov,
                                trazas=trazas)
                    s.add(p)
                    s.flush()
                else:
                    p = s.get(Producto, prod_id)
                    p.nombre = nombre
                    p.descripcion = desc
                    p.humedad_final = humedad_f
                    p.critico = critico
                    p.es_vendible = vendible
                    p.porcion_g = porcion_g
                    p.gramaje_g = gramaje_g
                    p.semanas_caducidad_override = semanas_ov
                    p.trazas = trazas
                    p.receta_ingredientes = []
                    p.receta_productos = []
                    p.costos_operativos = []
                    s.flush()

                for fila in self._prod_receta_ing:
                    s.add(RecetaIngrediente(
                        producto_id=p.id,
                        ingrediente_id=fila["ing_id"],
                        proporcion=fila["pct"] / 100.0,
                    ))
                for fila in self._prod_receta_prod:
                    s.add(RecetaProducto(
                        padre_id=p.id,
                        hijo_id=fila["prod_id"],
                        proporcion=fila["pct"] / 100.0,
                    ))
                for i, fila in enumerate(self._prod_costos, 1):
                    valor_db = (fila["valor"] / 100.0 if fila["tipo"] == "porcentual"
                                else fila["valor"])
                    s.add(CostoOperativo(
                        producto_id=p.id, nombre=fila["nombre"],
                        tipo=fila["tipo"], valor=valor_db, orden=i,
                    ))
                s.flush()

                p_l = s.get(Producto, p.id, options=self._selectinload_completo())
                tabla_100g   = p_l.tabla_nutricional_100g()
                tabla_p      = p_l.tabla_nutricional_porcion()
                merma_pct    = p_l.merma() * 100.0
                factor       = p_l.factor_concentracion()
                costo_kg     = p_l.costo_final_kg()
                nombre_p     = p_l.nombre
                porcion_final = p_l.porcion_g
                critico_p    = p_l.critico
                critico_auto = p_l.critico_calculado()
                humedad_pct  = p_l.humedad_final * 100.0
                micros       = p_l.tabla_micronutrientes_filtrada()
                descs        = p_l.evaluar_descriptores_micronutrientes()
                ficha        = consolidar_etiquetado(p_l)

                cad_info = {
                    "prod_id": p.id,
                    "efectiva": p_l.semanas_caducidad_efectiva(),
                    "calculada": p_l.semanas_caducidad_calculada(),
                    "override": p_l.semanas_caducidad_override,
                }

                s.commit()

            messagebox.showinfo("✅ Guardado", f"Producto '{nombre_p}' guardado correctamente.")
            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre_p}",
                nombre_p, tabla_100g, tabla_p,
                porcion_final, merma_pct, factor, costo_kg,
                critico=critico_p, critico_auto=critico_auto,
                humedad_final_pct=humedad_pct, micronutrientes=micros,
                descriptores=descs, caducidad_info=cad_info, ficha=ficha)
            self.mostrar_detalle_producto(cad_info["prod_id"])

        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror("Duplicado", "Ya existe un Producto con ese nombre.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    def _ver_tabla_prod(self, prod_id):
        try:
            with Session(engine) as s:
                p = s.get(Producto, prod_id, options=self._selectinload_completo())
                if p is None:
                    messagebox.showerror("Error", "Producto no encontrado.")
                    return
                tabla_100g   = p.tabla_nutricional_100g()
                tabla_p      = p.tabla_nutricional_porcion()
                merma_pct    = p.merma() * 100.0
                factor       = p.factor_concentracion()
                costo        = p.costo_final_kg()
                nombre       = p.nombre
                porcion_g    = p.porcion_g
                critico      = p.critico
                critico_auto = p.critico_calculado()
                humedad_pct  = p.humedad_final * 100.0
                micros       = p.tabla_micronutrientes_filtrada()
                descs        = p.evaluar_descriptores_micronutrientes()
                ficha        = consolidar_etiquetado(p)

                cad_info = {
                    "prod_id": prod_id,
                    "efectiva": p.semanas_caducidad_efectiva(),
                    "calculada": p.semanas_caducidad_calculada(),
                    "override": p.semanas_caducidad_override,
                }

            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre}",
                nombre, tabla_100g, tabla_p, porcion_g, merma_pct, factor, costo,
                critico=critico, critico_auto=critico_auto,
                humedad_final_pct=humedad_pct, micronutrientes=micros,
                descriptores=descs, caducidad_info=cad_info, ficha=ficha)
            self.mostrar_detalle_producto(prod_id)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # NORMATIVAS
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_vista_normativas_vacia(self):
        """
        El árbol ya expone la carpeta "Normativas", pero el módulo de gestión
        (CRUD de normativas propias) todavía no existe — calcular_sellos()
        sigue viva y se usa igual dentro de la Tabla Nutricional. Esto es solo
        el placeholder de la carpeta en el explorador.
        """
        self.limpiar_pantalla()
        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text="📋", font=("Segoe UI", 40), bg=COLOR_BG).pack(pady=(60, 10))
        tk.Label(frame, text="Módulo de Normativas en desarrollo / Próximamente",
                 font=FONT_BOLD, bg=COLOR_BG, fg="#757575").pack()
        self._boton(frame, "← Volver al Explorador", self.mostrar_menu_principal,
                    ancho=28).pack(pady=24)