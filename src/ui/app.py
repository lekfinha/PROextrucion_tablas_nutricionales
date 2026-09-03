import tkinter as tk
from tkinter import ttk, messagebox
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from src.database import engine
from src.models.ingrediente import Ingrediente
from src.models.subproducto import (SubProducto, SubProductoIngrediente,
                                     CostoOperativo, NUTRIENTES)
from src.models.producto_final import (ProductoFinal, ProductoFinalSubProducto,
                                        CostoOperativoPT, ETIQUETAS_NUTRIENTES)
from src.normativas import calcular_sellos, listar_normativas, NORMATIVAS_DISPONIBLES

# ── Paleta y fuentes ───────────────────────────────────────────────────────────
COLOR_BG     = "#F5F5F5"
COLOR_ACENTO = "#2C7BE5"
COLOR_PELIGRO= "#E53935"
COLOR_EXITO  = "#43A047"
COLOR_TEXTO  = "#212121"
FONT_TITULO  = ("Segoe UI", 15, "bold")
FONT_NORMAL  = ("Segoe UI", 10)
FONT_PEQUEÑA = ("Segoe UI", 9)
FONT_BOLD    = ("Segoe UI", 10, "bold")


class AppNutricion(tk.Tk):
    """Aplicación principal — Gestor Nutricional Pro Extrusion."""

    def __init__(self):
        super().__init__()
        self.title("Gestor Nutricional — Pro Extrusion")
        self.geometry("720x780")
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
            "colesterol_mg":          ("Colesterol (mg)",                float),
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
        self.mapa_ingredientes:      dict[str, int] = {}
        self.mapa_subproductos:      dict[str, int] = {}
        self.mapa_productos_finales: dict[str, int] = {}
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
        self.ingrediente_actual_id = None

    def _titulo(self, parent: tk.Widget, texto: str) -> tk.Label:
        lbl = tk.Label(parent, text=texto, font=FONT_TITULO, bg=COLOR_BG, fg=COLOR_TEXTO)
        lbl.pack(pady=(16, 8))
        return lbl

    def _boton(self, parent: tk.Widget, texto: str, comando,
               color_bg: str = "#E0E0E0", color_fg: str = COLOR_TEXTO,
               ancho: int = 28) -> tk.Button:
        return tk.Button(parent, text=texto, command=comando,
                         bg=color_bg, fg=color_fg, font=FONT_NORMAL,
                         width=ancho, relief="flat", cursor="hand2",
                         activebackground=color_bg, activeforeground=color_fg,
                         pady=6)

    def _separador(self, parent: tk.Widget):
        tk.Frame(parent, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=6)

    def _crear_scroll_frame(self, parent: tk.Widget):
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
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return outer, inner, canvas

    def _barra_botones(self, volver_cmd, guardar_cmd, guardar_texto="💾  Guardar"):
        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(frame, "← Volver", volver_cmd, ancho=14).pack(side="left", padx=(0, 6))
        self._boton(frame, guardar_texto, guardar_cmd,
                    color_bg=COLOR_EXITO, color_fg="white", ancho=22).pack(side="right")
        return frame

    def _combobox_buscable(self, parent: tk.Widget, opciones: list[str],
                           callback) -> ttk.Combobox:
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
                # Abrir el dropdown SIN mover el foco del entry
                try:
                    combo.tk.eval(f"ttk::combobox::Post {combo}")
                except Exception:
                    pass  # si falla (Tcl antiguo), simplemente no abre

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

    def _recargar_mapa_subproductos(self):
        with Session(engine) as s:
            sps = s.query(SubProducto).order_by(SubProducto.nombre).all()
            self.mapa_subproductos = {sp.nombre: sp.id for sp in sps}

    def _crear_combobox_sp(self, parent, callback):
        self._recargar_mapa_subproductos()
        return self._combobox_buscable(parent, sorted(self.mapa_subproductos), callback)

    def _recargar_mapa_pf(self):
        with Session(engine) as s:
            pfs = s.query(ProductoFinal).order_by(ProductoFinal.nombre).all()
            self.mapa_productos_finales = {pf.nombre: pf.id for pf in pfs}

    def _crear_combobox_pf(self, parent, callback):
        self._recargar_mapa_pf()
        return self._combobox_buscable(parent, sorted(self.mapa_productos_finales), callback)

    # ══════════════════════════════════════════════════════════════════════════
    # VENTANA TABLA NUTRICIONAL + SELLOS
    # ══════════════════════════════════════════════════════════════════════════

    def _mostrar_toplevel_nutricional(self, titulo_ventana: str, nombre_producto: str,
                                      tabla_100g: dict, tabla_porcion: dict,
                                      porcion_g: float, merma_pct: float,
                                      factor: float, costo_kg: float,
                                      critico: bool = False):
        top = tk.Toplevel(self)
        top.title(titulo_ventana)
        top.geometry("700x750")
        top.config(bg=COLOR_BG)
        top.resizable(True, True)

        tk.Label(top, text=nombre_producto, font=FONT_TITULO, bg=COLOR_BG).pack(pady=(14, 2))
        crit_txt = "Sí" if critico else "No"
        info = (f"Crítico: {crit_txt}  |  Merma: {merma_pct:.4f}%  |  Factor: ×{factor:.5f}  |  "
                f"Costo final: ${costo_kg:,.2f} /kg")
        tk.Label(top, text=info, font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#555555").pack()
        tk.Frame(top, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=8)

        # ── Tabla nutricional ─────────────────────────────────────────────────
        frame_tree = tk.Frame(top, bg=COLOR_BG)
        frame_tree.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        col_p = f"Por {porcion_g:.0f} g"
        tree = ttk.Treeview(frame_tree, columns=("nut", "c100", "cpor"),
                            show="headings", height=16)
        tree.heading("nut", text="Nutriente")
        tree.heading("c100", text="Por 100 g")
        tree.heading("cpor", text=col_p)
        tree.column("nut",  width=295)
        tree.column("c100", width=110, anchor="center")
        tree.column("cpor", width=110, anchor="center")

        sb = ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for key in NUTRIENTES:
            label = ETIQUETAS_NUTRIENTES.get(key, key)
            v100 = tabla_100g.get(key, 0.0)
            vpor = tabla_porcion.get(key, 0.0)
            tree.insert("", "end", values=(label, f"{v100:.4f}", f"{vpor:.4f}"))

        # ── Sección de sellos / destacadores ──────────────────────────────────
        tk.Frame(top, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=4)
        frame_norm = tk.Frame(top, bg=COLOR_BG)
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

        frame_sellos = tk.Frame(top, bg=COLOR_BG)
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

        # Tag styling for results
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
        self.limpiar_pantalla()
        self._titulo(self.container, "Menú Principal")
        tk.Label(self.container,
                 text="Sistema de Gestión Nutricional — Pro Extrusion",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(pady=(0, 16))

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack()

        self._boton(frame, "📦  Gestionar Ingredientes",
                    self.mostrar_menu_ingredientes,
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)
        self._boton(frame, "🧪  Gestionar SubProductos",
                    self.mostrar_menu_subproductos).pack(pady=5)
        self._boton(frame, "🏭  Gestionar Producto Final",
                    self.mostrar_menu_producto_final).pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=12)

        self._boton(frame, "📋  Normativas de Etiquetado",
                    self.mostrar_menu_normativas).pack(pady=5)

    # ══════════════════════════════════════════════════════════════════════════
    # INGREDIENTES — MENÚ + CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_ingredientes(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "📦 Gestionar Ingredientes")

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(pady=10)

        self._boton(frame, "➕  Agregar Ingrediente",
                    self.mostrar_menu_agregar,
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)
        self._boton(frame, "✏️  Modificar Ingrediente",
                    lambda: self.mostrar_formulario("modificar")).pack(pady=5)
        self._boton(frame, "🗑️  Eliminar Ingrediente",
                    self.mostrar_vista_eliminar,
                    color_bg=COLOR_PELIGRO, color_fg="white").pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=12)
        self._boton(frame, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=5)

    def mostrar_menu_agregar(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Agregar Ingrediente")

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(pady=10)

        self._boton(frame, "📄  Crear ingrediente desde cero",
                    lambda: self.mostrar_formulario("crear_nuevo"),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=8)
        self._boton(frame, "📋  Crear a partir de uno existente",
                    lambda: self.mostrar_formulario("crear_desde_existente")).pack(pady=8)

        tk.Frame(self.container, bg="#BDBDBD", height=1).pack(fill="x", padx=40, pady=20)
        self._boton(self.container, "← Volver",
                    self.mostrar_menu_ingredientes, ancho=30).pack()

    def mostrar_formulario(self, modo: str):
        self.limpiar_pantalla()
        self._critico_var = tk.BooleanVar(value=False)
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

        destino = (self.mostrar_menu_agregar
                   if modo in ("crear_nuevo", "crear_desde_existente")
                   else self.mostrar_menu_ingredientes)
        self._barra_botones(destino, lambda: self.guardar_ingrediente(modo),
                            "💾  Guardar Ingrediente")
        self._separador(self.container)

        outer, frame_form, _ = self._crear_scroll_frame(self.container)
        outer.pack(fill="both", expand=True, padx=20)

        # Checkbox Crítico
        row_crit = tk.Frame(frame_form, bg=COLOR_BG)
        row_crit.pack(fill="x", pady=6, padx=4)
        tk.Checkbutton(row_crit, text="  Crítico",
                       variable=self._critico_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")
        tk.Label(row_crit, text="(aplica sellos de advertencia)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(side="left", padx=8)

        for key, (label_text, _) in self.campos_formulario.items():
            row = tk.Frame(frame_form, bg=COLOR_BG)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=label_text, font=FONT_NORMAL, bg=COLOR_BG,
                     fg=COLOR_TEXTO, width=26, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            entry.pack(side="right", expand=True, fill="x")
            self.entries[key] = entry

    def cargar_datos_en_formulario(self, event=None):
        seleccion = self.combo_busqueda.get()
        if not seleccion or seleccion not in self.mapa_ingredientes:
            return
        self.ingrediente_actual_id = self.mapa_ingredientes[seleccion]
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

    def guardar_ingrediente(self, modo: str):
        try:
            datos: dict = {}
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

            with Session(engine) as s:
                if modo == "modificar":
                    if not self.ingrediente_actual_id:
                        raise ValueError("Debes seleccionar un ingrediente para modificar.")
                    ing = s.get(Ingrediente, self.ingrediente_actual_id)
                    for k, v in datos.items():
                        setattr(ing, k, v)
                else:
                    s.add(Ingrediente(**datos))
                s.commit()

            messagebox.showinfo("✅ Éxito", "Ingrediente guardado correctamente.")
            self.mostrar_menu_ingredientes()
        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror("Duplicado", "Ya existe un ingrediente con ese nombre y fabricante.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    def mostrar_vista_eliminar(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Eliminar Ingrediente")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(fb, text="🔍  Buscar ingrediente a eliminar:",
                 font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        self.combo_busqueda = self._crear_combobox_buscable(fb, self.seleccionar_para_eliminar)
        self.combo_busqueda.pack(fill="x", pady=4)

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(fbot, "← Volver", self.mostrar_menu_ingredientes, ancho=14).pack(side="left")
        self._boton(fbot, "🗑️  Eliminar", self.eliminar_ingrediente,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=16).pack(side="right")
        self._separador(self.container)

        self.lbl_advertencia = tk.Label(
            self.container, text="Selecciona un ingrediente para eliminarlo.",
            fg="#757575", font=FONT_NORMAL, bg=COLOR_BG, wraplength=480, justify="center")
        self.lbl_advertencia.pack(pady=30)

    def seleccionar_para_eliminar(self, event=None):
        seleccion = self.combo_busqueda.get()
        if not seleccion or seleccion not in self.mapa_ingredientes:
            return
        self.ingrediente_actual_id = self.mapa_ingredientes[seleccion]
        self.lbl_advertencia.config(
            text=f"⚠️  ¿Estás seguro de eliminar?\n\n«{seleccion}»\n\nEsta acción no se puede deshacer.",
            fg=COLOR_PELIGRO, font=("Segoe UI", 10, "bold"))

    def eliminar_ingrediente(self):
        if not self.ingrediente_actual_id:
            messagebox.showerror("Sin selección", "Selecciona un ingrediente primero.")
            return
        if not messagebox.askyesno("Confirmar eliminación",
                                   "¿Estás absolutamente seguro?\n\nEsta acción es irreversible."):
            return
        try:
            with Session(engine) as s:
                ing = s.get(Ingrediente, self.ingrediente_actual_id)
                if ing:
                    s.delete(ing)
                    s.commit()
            messagebox.showinfo("✅ Eliminado", "Ingrediente eliminado correctamente.")
            self.mostrar_menu_ingredientes()
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # SUBPRODUCTOS
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_subproductos(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "🧪 SubProductos")

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(pady=10)

        self._boton(frame, "🧪  Crear SubProducto",
                    lambda: self.mostrar_formulario_subproducto('crear'),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)
        self._boton(frame, "✏️  Editar SubProducto",
                    lambda: self._seleccionar_sp_y_hacer(
                        lambda sid: self.mostrar_formulario_subproducto('editar', sid))).pack(pady=5)
        self._boton(frame, "📊  Ver Tabla Nutricional",
                    lambda: self._seleccionar_sp_y_hacer(self._ver_tabla_sp)).pack(pady=5)
        self._boton(frame, "🗑️  Eliminar SubProducto",
                    self.mostrar_vista_eliminar_sp,
                    color_bg=COLOR_PELIGRO, color_fg="white").pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=12)
        self._boton(frame, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=5)

    def _seleccionar_sp_y_hacer(self, callback):
        self.limpiar_pantalla()
        self._titulo(self.container, "Seleccionar SubProducto")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=10)
        tk.Label(fb, text="🔍  Buscar SubProducto:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        combo = self._crear_combobox_sp(fb, lambda e: None)
        combo.pack(fill="x", pady=4)

        def _hacer():
            nombre = combo.get()
            if not nombre or nombre not in self.mapa_subproductos:
                messagebox.showerror("Error", "Selecciona un SubProducto válido.")
                return
            callback(self.mapa_subproductos[nombre])

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=10)
        self._boton(fbot, "← Volver", self.mostrar_menu_subproductos, ancho=14).pack(side="left")
        self._boton(fbot, "✓ Seleccionar", _hacer,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=16).pack(side="right")

    # ── Formulario crear/editar SubProducto ──────────────────────────────────

    def mostrar_formulario_subproducto(self, modo: str, sp_id: int | None = None):
        self.limpiar_pantalla()
        self._sp_receta: list[dict] = []
        self._sp_costos: list[dict] = []
        self._critico_var = tk.BooleanVar(value=False)

        titulo = "Nuevo SubProducto" if modo == 'crear' else "Editar SubProducto"
        self._titulo(self.container, titulo)

        self._barra_botones(self.mostrar_menu_subproductos,
                            lambda: self._guardar_subproducto(modo, sp_id),
                            "💾  Guardar SubProducto")
        self._separador(self.container)

        outer, frame_form, _ = self._crear_scroll_frame(self.container)
        outer.pack(fill="both", expand=True, padx=10)

        # ── Sección 1: Datos generales ──
        lf1 = tk.LabelFrame(frame_form, text=" Datos Generales ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf1.pack(fill="x", padx=5, pady=5)

        self._sp_entries: dict[str, tk.Entry] = {}
        for key, label in [("nombre",        "Nombre:"),
                            ("descripcion",   "Descripción (opcional):"),
                            ("humedad_final", "Humedad final (%, ej: 3.0):")]:
            row = tk.Frame(lf1, bg=COLOR_BG)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=label, font=FONT_NORMAL, bg=COLOR_BG,
                     width=28, anchor="w").pack(side="left")
            e = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            e.pack(side="right", expand=True, fill="x")
            self._sp_entries[key] = e

        row_crit = tk.Frame(lf1, bg=COLOR_BG)
        row_crit.pack(fill="x", padx=8, pady=3)
        tk.Checkbutton(row_crit, text="  Crítico",
                       variable=self._critico_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")
        tk.Label(row_crit, text="(aplica sellos de advertencia)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(side="left", padx=8)

        # ── Sección 2: Receta de ingredientes ──
        lf2 = tk.LabelFrame(frame_form, text=" Receta de Ingredientes (% en peso) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf2.pack(fill="x", padx=5, pady=5)

        fa = tk.Frame(lf2, bg=COLOR_BG)
        fa.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa, text="Ingrediente:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._sp_combo_ing = self._crear_combobox_buscable(fa, lambda e: None)
        self._sp_combo_ing.pack(side="left", padx=4)
        tk.Label(fa, text="%:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._sp_e_pct_ing = tk.Entry(fa, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._sp_e_pct_ing.pack(side="left", padx=4)
        self._boton(fa, "➕", self._sp_agregar_ing,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left")

        ft = tk.Frame(lf2, bg=COLOR_BG)
        ft.pack(fill="x", padx=8, pady=2)
        self._sp_tree_receta = ttk.Treeview(ft,
            columns=("ingrediente", "pct"), show="headings", height=5)
        self._sp_tree_receta.heading("ingrediente", text="Ingrediente")
        self._sp_tree_receta.heading("pct", text="%")
        self._sp_tree_receta.column("ingrediente", width=360)
        self._sp_tree_receta.column("pct", width=80, anchor="center")
        sb_i = ttk.Scrollbar(ft, orient="vertical", command=self._sp_tree_receta.yview)
        self._sp_tree_receta.configure(yscrollcommand=sb_i.set)
        self._sp_tree_receta.pack(side="left", fill="x", expand=True)
        sb_i.pack(side="right", fill="y")

        fc = tk.Frame(lf2, bg=COLOR_BG)
        fc.pack(fill="x", padx=8, pady=(2, 8))
        self._sp_lbl_total = tk.Label(fc, text="Total: 0.00%",
                                      font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_PELIGRO)
        self._sp_lbl_total.pack(side="left")
        self._boton(fc, "🗑️ Quitar fila", self._sp_quitar_ing,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        # ── Sección 3: Cascada de costos ──
        lf3 = tk.LabelFrame(frame_form, text=" Costos Operativos (cascada secuencial) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf3.pack(fill="x", padx=5, pady=5)

        fa3 = tk.Frame(lf3, bg=COLOR_BG)
        fa3.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa3, text="Nombre:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._sp_e_cnombre = tk.Entry(fa3, font=FONT_NORMAL, width=14, relief="solid", bd=1)
        self._sp_e_cnombre.pack(side="left", padx=3)
        tk.Label(fa3, text="Tipo:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._sp_cb_ctipo = ttk.Combobox(fa3, values=["porcentual", "fijo"],
                                          state="readonly", width=10, font=FONT_NORMAL)
        self._sp_cb_ctipo.set("porcentual")
        self._sp_cb_ctipo.pack(side="left", padx=3)
        tk.Label(fa3, text="Valor:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._sp_e_cvalor = tk.Entry(fa3, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._sp_e_cvalor.pack(side="left", padx=3)
        tk.Label(fa3, text="(% o $/kg)", font=FONT_PEQUEÑA, bg=COLOR_BG,
                 fg="#757575").pack(side="left", padx=2)
        self._boton(fa3, "➕", self._sp_agregar_costo,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left", padx=4)

        ft3 = tk.Frame(lf3, bg=COLOR_BG)
        ft3.pack(fill="x", padx=8, pady=2)
        self._sp_tree_costos = ttk.Treeview(ft3,
            columns=("orden", "nombre", "tipo", "valor"), show="headings", height=5)
        self._sp_tree_costos.heading("orden", text="#")
        self._sp_tree_costos.heading("nombre", text="Proceso")
        self._sp_tree_costos.heading("tipo", text="Tipo")
        self._sp_tree_costos.heading("valor", text="Valor")
        self._sp_tree_costos.column("orden", width=30, anchor="center")
        self._sp_tree_costos.column("nombre", width=200)
        self._sp_tree_costos.column("tipo", width=100, anchor="center")
        self._sp_tree_costos.column("valor", width=100, anchor="center")
        sb_c = ttk.Scrollbar(ft3, orient="vertical", command=self._sp_tree_costos.yview)
        self._sp_tree_costos.configure(yscrollcommand=sb_c.set)
        self._sp_tree_costos.pack(side="left", fill="x", expand=True)
        sb_c.pack(side="right", fill="y")

        fc3 = tk.Frame(lf3, bg=COLOR_BG)
        fc3.pack(fill="x", padx=8, pady=(2, 8))
        self._boton(fc3, "🗑️ Quitar paso", self._sp_quitar_costo,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        if modo == 'editar' and sp_id:
            self._sp_cargar_existente(sp_id)

    # ── Helpers del formulario SP ─────────────────────────────────────────────

    def _sp_refrescar_tree_receta(self):
        for item in self._sp_tree_receta.get_children():
            self._sp_tree_receta.delete(item)
        total = 0.0
        for fila in self._sp_receta:
            self._sp_tree_receta.insert("", "end",
                values=(fila["nombre"], f"{fila['pct']:.4f}"))
            total += fila["pct"]
        ok = abs(total - 100.0) < 0.01
        self._sp_lbl_total.config(
            text=f"Total: {total:.4f}%  {'✅' if ok else '⚠️ debe ser 100.00%'}",
            fg=COLOR_EXITO if ok else COLOR_PELIGRO)

    def _sp_agregar_ing(self):
        nombre = self._sp_combo_ing.get().strip()
        pct_str = self._sp_e_pct_ing.get().strip().replace(",", ".")
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
        for fila in self._sp_receta:
            if fila["ing_id"] == self.mapa_ingredientes[nombre]:
                fila["pct"] = pct
                self._sp_refrescar_tree_receta()
                self._sp_e_pct_ing.delete(0, tk.END)
                return
        self._sp_receta.append({"ing_id": self.mapa_ingredientes[nombre],
                                 "nombre": nombre, "pct": pct})
        self._sp_refrescar_tree_receta()
        self._sp_combo_ing.set("")
        self._sp_e_pct_ing.delete(0, tk.END)

    def _sp_quitar_ing(self):
        sel = self._sp_tree_receta.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona una fila para quitar.")
            return
        nombre = self._sp_tree_receta.item(sel[0])["values"][0]
        self._sp_receta = [f for f in self._sp_receta if f["nombre"] != nombre]
        self._sp_refrescar_tree_receta()

    def _sp_refrescar_tree_costos(self):
        for item in self._sp_tree_costos.get_children():
            self._sp_tree_costos.delete(item)
        for i, fila in enumerate(self._sp_costos, 1):
            vd = (f"{fila['valor']:.4f}%" if fila["tipo"] == "porcentual"
                  else f"${fila['valor']:,.2f}")
            self._sp_tree_costos.insert("", "end",
                values=(i, fila["nombre"], fila["tipo"], vd))

    def _sp_agregar_costo(self):
        nombre = self._sp_e_cnombre.get().strip()
        tipo = self._sp_cb_ctipo.get()
        valor_str = self._sp_e_cvalor.get().strip().replace(",", ".")
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
        self._sp_costos.append({"nombre": nombre, "tipo": tipo, "valor": valor})
        self._sp_refrescar_tree_costos()
        self._sp_e_cnombre.delete(0, tk.END)
        self._sp_e_cvalor.delete(0, tk.END)

    def _sp_quitar_costo(self):
        sel = self._sp_tree_costos.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona un paso para quitar.")
            return
        orden = int(self._sp_tree_costos.item(sel[0])["values"][0]) - 1
        self._sp_costos.pop(orden)
        self._sp_refrescar_tree_costos()

    def _sp_cargar_existente(self, sp_id: int):
        with Session(engine) as s:
            sp = s.get(SubProducto, sp_id, options=[
                selectinload(SubProducto.receta_ingredientes)
                    .selectinload(SubProductoIngrediente.ingrediente),
                selectinload(SubProducto.costos_operativos),
            ])
            if sp is None:
                return
            self._sp_entries["nombre"].insert(0, sp.nombre)
            self._sp_entries["descripcion"].insert(0, sp.descripcion or "")
            self._sp_entries["humedad_final"].insert(0, str(round(sp.humedad_final * 100.0, 6)))
            self._critico_var.set(sp.critico)
            for rel in sp.receta_ingredientes:
                self._sp_receta.append({
                    "ing_id": rel.ingrediente_id,
                    "nombre": rel.ingrediente.id_unico,
                    "pct":    round(rel.proporcion * 100.0, 6),
                })
            for co in sp.costos_operativos:
                self._sp_costos.append({
                    "nombre": co.nombre,
                    "tipo":   co.tipo,
                    "valor":  round(co.valor * 100.0, 6) if co.tipo == "porcentual" else co.valor,
                })
        self._sp_refrescar_tree_receta()
        self._sp_refrescar_tree_costos()

    def _guardar_subproducto(self, modo: str, sp_id: int | None):
        try:
            nombre = self._sp_entries["nombre"].get().strip()
            desc = self._sp_entries["descripcion"].get().strip()
            h_str = self._sp_entries["humedad_final"].get().strip().replace(",", ".")
            critico = self._critico_var.get()

            if not nombre:
                raise ValueError("El nombre del SubProducto no puede estar vacío.")
            if not self._sp_receta:
                raise ValueError("Agrega al menos un ingrediente a la receta.")

            humedad_f = float(h_str) / 100.0 if h_str else 0.0
            total_pct = sum(f["pct"] for f in self._sp_receta)
            if abs(total_pct - 100.0) > 0.01:
                raise ValueError(
                    f"Los porcentajes de la receta deben sumar 100%.\n"
                    f"Total actual: {total_pct:.4f}%")

            with Session(engine) as s:
                if modo == "crear":
                    sp = SubProducto(nombre=nombre, descripcion=desc,
                                     humedad_final=humedad_f, critico=critico)
                    s.add(sp)
                    s.flush()
                else:
                    sp = s.get(SubProducto, sp_id)
                    sp.nombre = nombre
                    sp.descripcion = desc
                    sp.humedad_final = humedad_f
                    sp.critico = critico
                    sp.receta_ingredientes = []
                    sp.costos_operativos = []
                    s.flush()

                for fila in self._sp_receta:
                    s.add(SubProductoIngrediente(
                        subproducto_id=sp.id,
                        ingrediente_id=fila["ing_id"],
                        proporcion=fila["pct"] / 100.0,
                    ))
                for i, fila in enumerate(self._sp_costos, 1):
                    valor_db = (fila["valor"] / 100.0 if fila["tipo"] == "porcentual"
                                else fila["valor"])
                    s.add(CostoOperativo(
                        subproducto_id=sp.id, nombre=fila["nombre"],
                        tipo=fila["tipo"], valor=valor_db, orden=i,
                    ))
                s.flush()

                sp_l = s.get(SubProducto, sp.id, options=[
                    selectinload(SubProducto.receta_ingredientes)
                        .selectinload(SubProductoIngrediente.ingrediente),
                    selectinload(SubProducto.costos_operativos),
                ])
                tabla_100g  = sp_l.tabla_nutricional()
                tabla_p     = sp_l.tabla_nutricional_porcion(25.0)
                merma_pct   = sp_l.merma() * 100.0
                factor      = sp_l.factor_concentracion()
                costo_kg    = sp_l.costo_final_kg()
                nombre_sp   = sp_l.nombre
                critico_sp  = sp_l.critico

                s.commit()

            messagebox.showinfo("✅ Guardado", f"SubProducto '{nombre_sp}' guardado correctamente.")
            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre_sp}",
                nombre_sp, tabla_100g, tabla_p, 25.0, merma_pct, factor, costo_kg,
                critico=critico_sp)
            self.mostrar_menu_subproductos()

        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror("Duplicado", "Ya existe un SubProducto con ese nombre.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    def _ver_tabla_sp(self, sp_id: int):
        try:
            with Session(engine) as s:
                sp = s.get(SubProducto, sp_id, options=[
                    selectinload(SubProducto.receta_ingredientes)
                        .selectinload(SubProductoIngrediente.ingrediente),
                    selectinload(SubProducto.costos_operativos),
                ])
                if sp is None:
                    messagebox.showerror("Error", "SubProducto no encontrado.")
                    return
                tabla_100g = sp.tabla_nutricional()
                tabla_p    = sp.tabla_nutricional_porcion(25.0)
                merma_pct  = sp.merma() * 100.0
                factor     = sp.factor_concentracion()
                costo      = sp.costo_final_kg()
                nombre     = sp.nombre
                critico    = sp.critico

            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre}",
                nombre, tabla_100g, tabla_p, 25.0, merma_pct, factor, costo,
                critico=critico)
            self.mostrar_menu_subproductos()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def mostrar_vista_eliminar_sp(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Eliminar SubProducto")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(fb, text="🔍  Buscar SubProducto a eliminar:",
                 font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        self._sp_combo_elim = self._crear_combobox_sp(fb, self._sp_seleccionar_elim)
        self._sp_combo_elim.pack(fill="x", pady=4)

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(fbot, "← Volver", self.mostrar_menu_subproductos, ancho=14).pack(side="left")
        self._boton(fbot, "🗑️  Eliminar", self._sp_eliminar,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=16).pack(side="right")
        self._separador(self.container)

        self._sp_lbl_adv = tk.Label(
            self.container, text="Selecciona un SubProducto para eliminarlo.",
            fg="#757575", font=FONT_NORMAL, bg=COLOR_BG, wraplength=480, justify="center")
        self._sp_lbl_adv.pack(pady=30)
        self._sp_id_elim: int | None = None

    def _sp_seleccionar_elim(self, event=None):
        nombre = self._sp_combo_elim.get()
        if not nombre or nombre not in self.mapa_subproductos:
            return
        self._sp_id_elim = self.mapa_subproductos[nombre]
        self._sp_lbl_adv.config(
            text=f"⚠️  ¿Eliminar SubProducto?\n\n«{nombre}»\n\nEsta acción no se puede deshacer.",
            fg=COLOR_PELIGRO, font=("Segoe UI", 10, "bold"))

    def _sp_eliminar(self):
        if not self._sp_id_elim:
            messagebox.showerror("Sin selección", "Selecciona un SubProducto primero.")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este SubProducto?\n\nEsta acción es irreversible."):
            return
        try:
            with Session(engine) as s:
                sp = s.get(SubProducto, self._sp_id_elim)
                if sp:
                    s.delete(sp)
                    s.commit()
            messagebox.showinfo("✅ Eliminado", "SubProducto eliminado correctamente.")
            self.mostrar_menu_subproductos()
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # PRODUCTO FINAL
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_producto_final(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "🏭 Producto Final")

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(pady=10)

        self._boton(frame, "🏭  Crear Producto Final",
                    lambda: self.mostrar_formulario_producto_final("crear"),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)
        self._boton(frame, "✏️  Editar Producto Final",
                    lambda: self._seleccionar_pf_y_hacer(
                        lambda pid: self.mostrar_formulario_producto_final("editar", pid))).pack(pady=5)
        self._boton(frame, "📊  Ver Tabla Nutricional",
                    lambda: self._seleccionar_pf_y_hacer(self._ver_tabla_pf)).pack(pady=5)
        self._boton(frame, "🗑️  Eliminar Producto Final",
                    self.mostrar_vista_eliminar_pf,
                    color_bg=COLOR_PELIGRO, color_fg="white").pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=12)
        self._boton(frame, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=5)

    def _seleccionar_pf_y_hacer(self, callback):
        self.limpiar_pantalla()
        self._titulo(self.container, "Seleccionar Producto Final")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=10)
        tk.Label(fb, text="🔍  Buscar Producto Final:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        combo = self._crear_combobox_pf(fb, lambda e: None)
        combo.pack(fill="x", pady=4)

        def _hacer():
            nombre = combo.get()
            if not nombre or nombre not in self.mapa_productos_finales:
                messagebox.showerror("Error", "Selecciona un Producto Final válido.")
                return
            callback(self.mapa_productos_finales[nombre])

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=10)
        self._boton(fbot, "← Volver", self.mostrar_menu_producto_final, ancho=14).pack(side="left")
        self._boton(fbot, "✓ Seleccionar", _hacer,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=16).pack(side="right")

    # ── Formulario crear/editar ProductoFinal ─────────────────────────────────

    def mostrar_formulario_producto_final(self, modo: str, pf_id: int | None = None):
        self.limpiar_pantalla()
        self._pf_receta: list[dict] = []
        self._pf_costos: list[dict] = []
        self._critico_var = tk.BooleanVar(value=False)

        titulo = "Nuevo Producto Final" if modo == "crear" else "Editar Producto Final"
        self._titulo(self.container, titulo)

        self._barra_botones(self.mostrar_menu_producto_final,
                            lambda: self._guardar_producto_final(modo, pf_id),
                            "💾  Guardar Producto Final")
        self._separador(self.container)

        outer, frame_form, _ = self._crear_scroll_frame(self.container)
        outer.pack(fill="both", expand=True, padx=10)

        # ── Sección 1: Datos generales ──
        lf1 = tk.LabelFrame(frame_form, text=" Datos Generales ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf1.pack(fill="x", padx=5, pady=5)

        self._pf_entries: dict[str, tk.Entry] = {}
        campos_pf = [
            ("nombre",        "Nombre del producto:"),
            ("descripcion",   "Descripción (opcional):"),
            ("porcion_g",     "Porción (g, ej: 25):"),
            ("gramaje_g",     "Gramaje empaque (g, ej: 200):"),
            ("humedad_final", "Humedad final (%, ej: 4.0):"),
        ]
        defaults = {"porcion_g": "25", "gramaje_g": "200", "humedad_final": "0"}
        for key, label in campos_pf:
            row = tk.Frame(lf1, bg=COLOR_BG)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=label, font=FONT_NORMAL, bg=COLOR_BG,
                     width=28, anchor="w").pack(side="left")
            e = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            if key in defaults:
                e.insert(0, defaults[key])
            e.pack(side="right", expand=True, fill="x")
            self._pf_entries[key] = e

        row_crit = tk.Frame(lf1, bg=COLOR_BG)
        row_crit.pack(fill="x", padx=8, pady=3)
        tk.Checkbutton(row_crit, text="  Crítico",
                       variable=self._critico_var,
                       font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXTO,
                       selectcolor="#FFFFFF", activebackground=COLOR_BG).pack(side="left")
        tk.Label(row_crit, text="(aplica sellos de advertencia)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(side="left", padx=8)

        # ── Sección 2: Composición de SubProductos ──
        lf2 = tk.LabelFrame(frame_form, text=" Composición de SubProductos (% en peso) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf2.pack(fill="x", padx=5, pady=5)

        fa2 = tk.Frame(lf2, bg=COLOR_BG)
        fa2.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa2, text="SubProducto:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._pf_combo_sp = self._crear_combobox_sp(fa2, lambda e: None)
        self._pf_combo_sp.pack(side="left", padx=4)
        tk.Label(fa2, text="%:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._pf_e_pct_sp = tk.Entry(fa2, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._pf_e_pct_sp.pack(side="left", padx=4)
        self._boton(fa2, "➕", self._pf_agregar_sp,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left")

        ft2 = tk.Frame(lf2, bg=COLOR_BG)
        ft2.pack(fill="x", padx=8, pady=2)
        self._pf_tree_receta = ttk.Treeview(ft2,
            columns=("subproducto", "pct"), show="headings", height=4)
        self._pf_tree_receta.heading("subproducto", text="SubProducto")
        self._pf_tree_receta.heading("pct", text="%")
        self._pf_tree_receta.column("subproducto", width=360)
        self._pf_tree_receta.column("pct", width=80, anchor="center")
        sb2 = ttk.Scrollbar(ft2, orient="vertical", command=self._pf_tree_receta.yview)
        self._pf_tree_receta.configure(yscrollcommand=sb2.set)
        self._pf_tree_receta.pack(side="left", fill="x", expand=True)
        sb2.pack(side="right", fill="y")

        fc2 = tk.Frame(lf2, bg=COLOR_BG)
        fc2.pack(fill="x", padx=8, pady=(2, 8))
        self._pf_lbl_total = tk.Label(fc2, text="Total: 0.00%",
                                      font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_PELIGRO)
        self._pf_lbl_total.pack(side="left")
        self._boton(fc2, "🗑️ Quitar fila", self._pf_quitar_sp,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        # ── Sección 3: Costos operativos del PT ──
        lf3 = tk.LabelFrame(frame_form, text=" Costos Operativos del PT (cascada secuencial) ",
                            bg=COLOR_BG, font=FONT_NORMAL, fg=COLOR_TEXTO)
        lf3.pack(fill="x", padx=5, pady=5)

        fa3 = tk.Frame(lf3, bg=COLOR_BG)
        fa3.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(fa3, text="Nombre:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._pf_e_cnombre = tk.Entry(fa3, font=FONT_NORMAL, width=14, relief="solid", bd=1)
        self._pf_e_cnombre.pack(side="left", padx=3)
        tk.Label(fa3, text="Tipo:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._pf_cb_ctipo = ttk.Combobox(fa3, values=["porcentual", "fijo"],
                                          state="readonly", width=10, font=FONT_NORMAL)
        self._pf_cb_ctipo.set("porcentual")
        self._pf_cb_ctipo.pack(side="left", padx=3)
        tk.Label(fa3, text="Valor:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(side="left")
        self._pf_e_cvalor = tk.Entry(fa3, font=FONT_NORMAL, width=8, relief="solid", bd=1)
        self._pf_e_cvalor.pack(side="left", padx=3)
        tk.Label(fa3, text="(% o $/kg)", font=FONT_PEQUEÑA, bg=COLOR_BG,
                 fg="#757575").pack(side="left", padx=2)
        self._boton(fa3, "➕", self._pf_agregar_costo,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=4).pack(side="left", padx=4)

        ft3 = tk.Frame(lf3, bg=COLOR_BG)
        ft3.pack(fill="x", padx=8, pady=2)
        self._pf_tree_costos = ttk.Treeview(ft3,
            columns=("orden", "nombre", "tipo", "valor"), show="headings", height=4)
        self._pf_tree_costos.heading("orden", text="#")
        self._pf_tree_costos.heading("nombre", text="Proceso")
        self._pf_tree_costos.heading("tipo", text="Tipo")
        self._pf_tree_costos.heading("valor", text="Valor")
        self._pf_tree_costos.column("orden", width=30, anchor="center")
        self._pf_tree_costos.column("nombre", width=200)
        self._pf_tree_costos.column("tipo", width=100, anchor="center")
        self._pf_tree_costos.column("valor", width=100, anchor="center")
        sb3 = ttk.Scrollbar(ft3, orient="vertical", command=self._pf_tree_costos.yview)
        self._pf_tree_costos.configure(yscrollcommand=sb3.set)
        self._pf_tree_costos.pack(side="left", fill="x", expand=True)
        sb3.pack(side="right", fill="y")

        fc3 = tk.Frame(lf3, bg=COLOR_BG)
        fc3.pack(fill="x", padx=8, pady=(2, 8))
        self._boton(fc3, "🗑️ Quitar paso", self._pf_quitar_costo,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=14).pack(side="right")

        if modo == "editar" and pf_id:
            self._pf_cargar_existente(pf_id)

    # ── Helpers del formulario PF ─────────────────────────────────────────────

    def _pf_refrescar_tree_receta(self):
        for item in self._pf_tree_receta.get_children():
            self._pf_tree_receta.delete(item)
        total = 0.0
        for fila in self._pf_receta:
            self._pf_tree_receta.insert("", "end",
                values=(fila["nombre"], f"{fila['pct']:.4f}"))
            total += fila["pct"]
        ok = abs(total - 100.0) < 0.01
        self._pf_lbl_total.config(
            text=f"Total: {total:.4f}%  {'✅' if ok else '⚠️ debe ser 100.00%'}",
            fg=COLOR_EXITO if ok else COLOR_PELIGRO)

    def _pf_agregar_sp(self):
        nombre = self._pf_combo_sp.get().strip()
        pct_str = self._pf_e_pct_sp.get().strip().replace(",", ".")
        if not nombre or nombre not in self.mapa_subproductos:
            messagebox.showerror("Error", "Selecciona un SubProducto válido de la lista.")
            return
        try:
            pct = float(pct_str)
            if pct <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingresa un porcentaje válido (número > 0).")
            return
        for fila in self._pf_receta:
            if fila["sp_id"] == self.mapa_subproductos[nombre]:
                fila["pct"] = pct
                self._pf_refrescar_tree_receta()
                self._pf_e_pct_sp.delete(0, tk.END)
                return
        self._pf_receta.append({"sp_id": self.mapa_subproductos[nombre],
                                 "nombre": nombre, "pct": pct})
        self._pf_refrescar_tree_receta()
        self._pf_combo_sp.set("")
        self._pf_e_pct_sp.delete(0, tk.END)

    def _pf_quitar_sp(self):
        sel = self._pf_tree_receta.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona una fila para quitar.")
            return
        nombre = self._pf_tree_receta.item(sel[0])["values"][0]
        self._pf_receta = [f for f in self._pf_receta if f["nombre"] != nombre]
        self._pf_refrescar_tree_receta()

    def _pf_refrescar_tree_costos(self):
        for item in self._pf_tree_costos.get_children():
            self._pf_tree_costos.delete(item)
        for i, fila in enumerate(self._pf_costos, 1):
            vd = (f"{fila['valor']:.4f}%" if fila["tipo"] == "porcentual"
                  else f"${fila['valor']:,.2f}")
            self._pf_tree_costos.insert("", "end",
                values=(i, fila["nombre"], fila["tipo"], vd))

    def _pf_agregar_costo(self):
        nombre = self._pf_e_cnombre.get().strip()
        tipo = self._pf_cb_ctipo.get()
        valor_str = self._pf_e_cvalor.get().strip().replace(",", ".")
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
        self._pf_costos.append({"nombre": nombre, "tipo": tipo, "valor": valor})
        self._pf_refrescar_tree_costos()
        self._pf_e_cnombre.delete(0, tk.END)
        self._pf_e_cvalor.delete(0, tk.END)

    def _pf_quitar_costo(self):
        sel = self._pf_tree_costos.selection()
        if not sel:
            messagebox.showerror("Sin selección", "Selecciona un paso para quitar.")
            return
        orden = int(self._pf_tree_costos.item(sel[0])["values"][0]) - 1
        self._pf_costos.pop(orden)
        self._pf_refrescar_tree_costos()

    def _pf_cargar_existente(self, pf_id: int):
        with Session(engine) as s:
            pf = s.get(ProductoFinal, pf_id, options=[
                selectinload(ProductoFinal.receta_subproductos)
                    .selectinload(ProductoFinalSubProducto.subproducto),
                selectinload(ProductoFinal.costos_operativos),
            ])
            if pf is None:
                return
            self._pf_entries["nombre"].insert(0, pf.nombre)
            self._pf_entries["descripcion"].insert(0, pf.descripcion or "")
            self._critico_var.set(pf.critico)
            for k, v in [("porcion_g", pf.porcion_g), ("gramaje_g", pf.gramaje_g)]:
                self._pf_entries[k].delete(0, tk.END)
                self._pf_entries[k].insert(0, str(v))
            self._pf_entries["humedad_final"].delete(0, tk.END)
            self._pf_entries["humedad_final"].insert(0, str(round(pf.humedad_final * 100.0, 6)))
            for rel in pf.receta_subproductos:
                self._pf_receta.append({
                    "sp_id":  rel.subproducto_id,
                    "nombre": rel.subproducto.nombre,
                    "pct":    round(rel.proporcion * 100.0, 6),
                })
            for co in pf.costos_operativos:
                self._pf_costos.append({
                    "nombre": co.nombre, "tipo": co.tipo,
                    "valor":  round(co.valor * 100.0, 6) if co.tipo == "porcentual" else co.valor,
                })
        self._pf_refrescar_tree_receta()
        self._pf_refrescar_tree_costos()

    def _guardar_producto_final(self, modo: str, pf_id: int | None):
        try:
            nombre  = self._pf_entries["nombre"].get().strip()
            desc    = self._pf_entries["descripcion"].get().strip()
            p_str   = self._pf_entries["porcion_g"].get().strip().replace(",", ".")
            g_str   = self._pf_entries["gramaje_g"].get().strip().replace(",", ".")
            h_str   = self._pf_entries["humedad_final"].get().strip().replace(",", ".")
            critico = self._critico_var.get()

            if not nombre:
                raise ValueError("El nombre del Producto Final no puede estar vacío.")
            if not self._pf_receta:
                raise ValueError("Agrega al menos un SubProducto a la composición.")

            porcion_g  = float(p_str) if p_str else 25.0
            gramaje_g  = float(g_str) if g_str else 200.0
            humedad_f  = float(h_str) / 100.0 if h_str else 0.0

            total_pct = sum(f["pct"] for f in self._pf_receta)
            if abs(total_pct - 100.0) > 0.01:
                raise ValueError(
                    f"Las proporciones deben sumar 100%.\nTotal actual: {total_pct:.4f}%")

            with Session(engine) as s:
                if modo == "crear":
                    pf = ProductoFinal(nombre=nombre, descripcion=desc,
                                       porcion_g=porcion_g, gramaje_g=gramaje_g,
                                       humedad_final=humedad_f, critico=critico)
                    s.add(pf)
                    s.flush()
                else:
                    pf = s.get(ProductoFinal, pf_id)
                    pf.nombre = nombre; pf.descripcion = desc
                    pf.porcion_g = porcion_g; pf.gramaje_g = gramaje_g
                    pf.humedad_final = humedad_f; pf.critico = critico
                    pf.receta_subproductos = []
                    pf.costos_operativos = []
                    s.flush()

                for fila in self._pf_receta:
                    s.add(ProductoFinalSubProducto(
                        productofinal_id=pf.id,
                        subproducto_id=fila["sp_id"],
                        proporcion=fila["pct"] / 100.0,
                    ))
                for i, fila in enumerate(self._pf_costos, 1):
                    valor_db = fila["valor"] / 100.0 if fila["tipo"] == "porcentual" else fila["valor"]
                    s.add(CostoOperativoPT(
                        productofinal_id=pf.id, nombre=fila["nombre"],
                        tipo=fila["tipo"], valor=valor_db, orden=i,
                    ))
                s.flush()

                pf_l = s.get(ProductoFinal, pf.id, options=[
                    selectinload(ProductoFinal.receta_subproductos)
                        .selectinload(ProductoFinalSubProducto.subproducto)
                        .selectinload(SubProducto.receta_ingredientes)
                        .selectinload(SubProductoIngrediente.ingrediente),
                    selectinload(ProductoFinal.receta_subproductos)
                        .selectinload(ProductoFinalSubProducto.subproducto)
                        .selectinload(SubProducto.costos_operativos),
                    selectinload(ProductoFinal.costos_operativos),
                ])
                tabla_100g   = pf_l.tabla_nutricional_100g()
                tabla_p      = pf_l.tabla_nutricional_porcion()
                merma_pct    = pf_l.merma() * 100.0
                factor       = pf_l.factor_concentracion()
                costo_kg     = pf_l.costo_final_kg()
                nombre_pf    = pf_l.nombre
                porcion_final = pf_l.porcion_g
                critico_pf   = pf_l.critico

                s.commit()

            messagebox.showinfo("✅ Guardado", f"Producto Final '{nombre_pf}' guardado correctamente.")
            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre_pf}",
                nombre_pf, tabla_100g, tabla_p,
                porcion_final, merma_pct, factor, costo_kg,
                critico=critico_pf)
            self.mostrar_menu_producto_final()

        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror("Duplicado", "Ya existe un Producto Final con ese nombre.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    def _ver_tabla_pf(self, pf_id: int):
        try:
            with Session(engine) as s:
                pf = s.get(ProductoFinal, pf_id, options=[
                    selectinload(ProductoFinal.receta_subproductos)
                        .selectinload(ProductoFinalSubProducto.subproducto)
                        .selectinload(SubProducto.receta_ingredientes)
                        .selectinload(SubProductoIngrediente.ingrediente),
                    selectinload(ProductoFinal.receta_subproductos)
                        .selectinload(ProductoFinalSubProducto.subproducto)
                        .selectinload(SubProducto.costos_operativos),
                    selectinload(ProductoFinal.costos_operativos),
                ])
                if pf is None:
                    messagebox.showerror("Error", "Producto Final no encontrado.")
                    return
                tabla_100g = pf.tabla_nutricional_100g()
                tabla_p    = pf.tabla_nutricional_porcion()
                merma_pct  = pf.merma() * 100.0
                factor     = pf.factor_concentracion()
                costo      = pf.costo_final_kg()
                nombre     = pf.nombre
                porcion_g  = pf.porcion_g
                critico    = pf.critico

            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre}",
                nombre, tabla_100g, tabla_p, porcion_g, merma_pct, factor, costo,
                critico=critico)
            self.mostrar_menu_producto_final()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def mostrar_vista_eliminar_pf(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Eliminar Producto Final")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(fb, text="🔍  Buscar Producto Final a eliminar:",
                 font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        self._pf_combo_elim = self._crear_combobox_pf(fb, self._pf_seleccionar_elim)
        self._pf_combo_elim.pack(fill="x", pady=4)

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(fbot, "← Volver", self.mostrar_menu_producto_final, ancho=14).pack(side="left")
        self._boton(fbot, "🗑️  Eliminar", self._pf_eliminar,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=16).pack(side="right")
        self._separador(self.container)

        self._pf_lbl_adv = tk.Label(
            self.container, text="Selecciona un Producto Final para eliminarlo.",
            fg="#757575", font=FONT_NORMAL, bg=COLOR_BG, wraplength=480, justify="center")
        self._pf_lbl_adv.pack(pady=30)
        self._pf_id_elim: int | None = None

    def _pf_seleccionar_elim(self, event=None):
        nombre = self._pf_combo_elim.get()
        if not nombre or nombre not in self.mapa_productos_finales:
            return
        self._pf_id_elim = self.mapa_productos_finales[nombre]
        self._pf_lbl_adv.config(
            text=f"⚠️  ¿Eliminar Producto Final?\n\n«{nombre}»\n\nEsta acción no se puede deshacer.",
            fg=COLOR_PELIGRO, font=("Segoe UI", 10, "bold"))

    def _pf_eliminar(self):
        if not self._pf_id_elim:
            messagebox.showerror("Sin selección", "Selecciona un Producto Final primero.")
            return
        if not messagebox.askyesno("Confirmar",
                                   "¿Eliminar este Producto Final?\n\nEsta acción es irreversible."):
            return
        try:
            with Session(engine) as s:
                pf = s.get(ProductoFinal, self._pf_id_elim)
                if pf:
                    s.delete(pf)
                    s.commit()
            messagebox.showinfo("✅ Eliminado", "Producto Final eliminado correctamente.")
            self.mostrar_menu_producto_final()
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # NORMATIVAS
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_normativas(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "📋 Normativas de Etiquetado")

        tk.Label(self.container,
                 text="Normativas disponibles para el cálculo de sellos y destacadores.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(pady=(0, 12))

        frame_list = tk.Frame(self.container, bg=COLOR_BG)
        frame_list.pack(fill="both", expand=True, padx=20)

        tree = ttk.Treeview(frame_list,
            columns=("nombre", "pais", "descripcion"), show="headings", height=8)
        tree.heading("nombre", text="Normativa")
        tree.heading("pais", text="País")
        tree.heading("descripcion", text="Descripción")
        tree.column("nombre", width=250)
        tree.column("pais", width=80, anchor="center")
        tree.column("descripcion", width=350)
        tree.pack(fill="both", expand=True)

        for nombre, info in NORMATIVAS_DISPONIBLES.items():
            tree.insert("", "end", values=(nombre, info["pais"], info["descripcion"]))

        tk.Label(self.container,
                 text="💡  Las normativas se calculan automáticamente al ver la tabla\n"
                      "nutricional de un SubProducto o Producto Final.\n\n"
                      "Para agregar una nueva normativa, contacte al desarrollador.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575",
                 justify="center", wraplength=500).pack(pady=16)

        self._boton(self.container, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=10)