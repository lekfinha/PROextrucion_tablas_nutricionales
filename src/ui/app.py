"""
Interfaz gráfica principal — Gestor Nutricional Pro Extrusion.

Usa el modelo unificado Producto (reemplaza SubProducto + ProductoFinal).
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from src.database import engine
from src.models.ingrediente import Ingrediente
from src.models.producto import (Producto, RecetaIngrediente, RecetaProducto,
                                  CostoOperativo, NUTRIENTES, ETIQUETAS_NUTRIENTES)
from src.models.micronutriente import Micronutriente, ProductoMicronutriente
from src.normativas import calcular_sellos, listar_normativas, NORMATIVAS_DISPONIBLES
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

    def _recargar_mapa_productos(self, tipo_filtro=None):
        with Session(engine) as s:
            q = s.query(Producto).order_by(Producto.nombre)
            if tipo_filtro:
                q = q.filter(Producto.tipo == tipo_filtro)
            prods = q.all()
            self.mapa_productos = {p.nombre: p.id for p in prods}

    def _crear_combobox_producto(self, parent, callback, tipo_filtro=None):
        self._recargar_mapa_productos(tipo_filtro)
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
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # VENTANA TABLA NUTRICIONAL + SELLOS
    # ══════════════════════════════════════════════════════════════════════════

    def _mostrar_toplevel_nutricional(self, titulo_ventana, nombre_producto,
                                      tabla_100g, tabla_porcion,
                                      porcion_g, merma_pct, factor, costo_kg,
                                      critico=False, critico_auto=False,
                                      humedad_final_pct=0.0,
                                      micronutrientes=None,
                                      caducidad_info=None):
        top = tk.Toplevel(self)
        top.title(titulo_ventana)
        top.geometry("740x820")
        top.config(bg=COLOR_BG)
        top.resizable(True, True)

        tk.Label(top, text=nombre_producto, font=FONT_TITULO, bg=COLOR_BG).pack(pady=(14, 2))

        # ── Cabecera: información de proceso (humedad separada) ──
        info_proceso = f"Humedad: {humedad_final_pct:.2f}%  |  Merma: {merma_pct:.4f}%  |  Factor: ×{factor:.5f}"
        tk.Label(top, text=info_proceso, font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#555555").pack()

        crit_txt = "Sí" if critico else "No"
        if critico != critico_auto:
            crit_txt += f"  ⚠️ (auto-detección sugiere {'Sí' if critico_auto else 'No'})"
        info_negocio = f"Crítico: {crit_txt}  |  Costo final: ${costo_kg:,.2f} /kg"
        tk.Label(top, text=info_negocio, font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#555555").pack()

        # ── Caducidad ──
        if caducidad_info:
            fecha_est = caducidad_info.get("fecha_estimada")
            proximos = caducidad_info.get("proximos", [])
            cad_txt = f"Caducidad estimada: {fecha_est}" if fecha_est else "Sin fechas de caducidad"
            tk.Label(top, text=cad_txt, font=FONT_PEQUEÑA, bg=COLOR_BG,
                     fg=COLOR_PELIGRO if fecha_est else "#757575").pack()
            if proximos:
                prox_txt = "  |  ".join(f"{n}: {f}" for n, f in proximos[:3])
                tk.Label(top, text=f"Próximos: {prox_txt}",
                         font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack()

        tk.Frame(top, bg="#BDBDBD", height=1).pack(fill="x", padx=20, pady=8)

        # ── Tabla nutricional con redondeo Minsal ──
        frame_tree = tk.Frame(top, bg=COLOR_BG)
        frame_tree.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        col_p = f"Por {porcion_g:.0f} g"
        tree = ttk.Treeview(frame_tree, columns=("nut", "c100", "cpor"),
                            show="headings", height=16)
        tree.heading("nut", text="Nutriente")
        tree.heading("c100", text="Por 100 g")
        tree.heading("cpor", text=col_p)
        tree.column("nut",  width=295)
        tree.column("c100", width=120, anchor="center")
        tree.column("cpor", width=120, anchor="center")

        sb = ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

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
                dest = " ★" if mn["destacado"] else ""
                label = f"    {mn['nombre']} ({mn['unidad']}){dest}"
                tree.insert("", "end", values=(
                    label,
                    redondear_minsal(mn["cantidad_100g"]),
                    f"{redondear_minsal(mn['cantidad_porcion'])} ({mn['pct_ddr']:.1f}% DDR)"))

        # ── Sección de sellos / destacadores ──
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
        self._boton(frame, "🧪  Gestionar Productos",
                    self.mostrar_menu_productos).pack(pady=5)

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

    def mostrar_formulario(self, modo):
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
        tk.Label(row_crit, text="(ingrediente aporta azúcar/sodio/grasa añadida)",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(side="left", padx=8)

        for key, (label_text, _) in self.campos_formulario.items():
            row = tk.Frame(frame_form, bg=COLOR_BG)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=label_text, font=FONT_NORMAL, bg=COLOR_BG,
                     fg=COLOR_TEXTO, width=26, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            entry.pack(side="right", expand=True, fill="x")
            self.entries[key] = entry

        # Trazabilidad: fecha vencimiento ficha y PDF
        self._separador(frame_form)
        tk.Label(frame_form, text="Trazabilidad", font=FONT_BOLD, bg=COLOR_BG).pack(anchor="w", padx=4)

        row_fv = tk.Frame(frame_form, bg=COLOR_BG)
        row_fv.pack(fill="x", pady=3, padx=4)
        tk.Label(row_fv, text="Vencimiento ficha (AAAA-MM-DD):", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_fecha_venc = tk.Entry(row_fv, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_fecha_venc.pack(side="right", expand=True, fill="x")

        row_pdf = tk.Frame(frame_form, bg=COLOR_BG)
        row_pdf.pack(fill="x", pady=3, padx=4)
        tk.Label(row_pdf, text="Ficha técnica (PDF):", font=FONT_NORMAL,
                 bg=COLOR_BG, width=26, anchor="w").pack(side="left")
        self._e_pdf_path = tk.Entry(row_pdf, font=FONT_NORMAL, relief="solid", bd=1)
        self._e_pdf_path.pack(side="left", expand=True, fill="x")
        self._boton(row_pdf, "📂", lambda: self._seleccionar_pdf(),
                    ancho=4).pack(side="right", padx=4)

    def _seleccionar_pdf(self):
        path = filedialog.askopenfilename(
            title="Seleccionar ficha técnica PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
            initialdir="data/fichas_tecnicas")
        if path:
            self._e_pdf_path.delete(0, tk.END)
            self._e_pdf_path.insert(0, path)

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
            # Trazabilidad
            self._e_fecha_venc.delete(0, tk.END)
            if ing.fecha_vencimiento_ficha:
                self._e_fecha_venc.insert(0, str(ing.fecha_vencimiento_ficha))
            self._e_pdf_path.delete(0, tk.END)
            if ing.ruta_pdf_ficha:
                self._e_pdf_path.insert(0, ing.ruta_pdf_ficha)

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
            fv_str = self._e_fecha_venc.get().strip()
            if fv_str:
                from datetime import date
                datos["fecha_vencimiento_ficha"] = date.fromisoformat(fv_str)
            pdf_str = self._e_pdf_path.get().strip()
            if pdf_str:
                datos["ruta_pdf_ficha"] = pdf_str

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
    # PRODUCTOS (modelo unificado — SubProductos + Productos Finales)
    # ══════════════════════════════════════════════════════════════════════════

    def mostrar_menu_productos(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "🧪 Gestionar Productos")

        frame = tk.Frame(self.container, bg=COLOR_BG)
        frame.pack(pady=10)

        self._boton(frame, "🧪  Crear SubProducto",
                    lambda: self.mostrar_formulario_producto('crear', 'subproducto'),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)
        self._boton(frame, "🏭  Crear Producto Final",
                    lambda: self.mostrar_formulario_producto('crear', 'producto_final'),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=8)

        self._boton(frame, "✏️  Editar Producto",
                    lambda: self._seleccionar_prod_y_hacer(
                        lambda pid: self.mostrar_formulario_producto('editar', None, pid))).pack(pady=5)
        self._boton(frame, "📊  Ver Tabla Nutricional",
                    lambda: self._seleccionar_prod_y_hacer(self._ver_tabla_prod)).pack(pady=5)
        self._boton(frame, "🗑️  Eliminar Producto",
                    self.mostrar_vista_eliminar_prod,
                    color_bg=COLOR_PELIGRO, color_fg="white").pack(pady=5)

        tk.Frame(frame, bg="#BDBDBD", height=1).pack(fill="x", pady=8)
        self._boton(frame, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=5)

    def _seleccionar_prod_y_hacer(self, callback):
        self.limpiar_pantalla()
        self._titulo(self.container, "Seleccionar Producto")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=10)
        tk.Label(fb, text="🔍  Buscar Producto:", font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        combo = self._crear_combobox_producto(fb, lambda e: None)
        combo.pack(fill="x", pady=4)

        def _hacer():
            nombre = combo.get()
            if not nombre or nombre not in self.mapa_productos:
                messagebox.showerror("Error", "Selecciona un Producto válido.")
                return
            callback(self.mapa_productos[nombre])

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=10)
        self._boton(fbot, "← Volver", self.mostrar_menu_productos, ancho=14).pack(side="left")
        self._boton(fbot, "✓ Seleccionar", _hacer,
                    color_bg=COLOR_ACENTO, color_fg="white", ancho=16).pack(side="right")

    # ── Formulario crear/editar Producto (unificado) ──────────────────────────

    def mostrar_formulario_producto(self, modo, tipo_prod=None, prod_id=None):
        self.limpiar_pantalla()
        self._prod_receta_ing: list[dict] = []
        self._prod_receta_prod: list[dict] = []
        self._prod_costos: list[dict] = []
        self._critico_var = tk.BooleanVar(value=False)

        if modo == 'editar' and prod_id:
            with Session(engine) as s:
                p = s.get(Producto, prod_id)
                tipo_prod = p.tipo if p else 'subproducto'

        es_pf = (tipo_prod == "producto_final")
        label_tipo = "Producto Final" if es_pf else "SubProducto"
        titulo = f"Nuevo {label_tipo}" if modo == 'crear' else f"Editar {label_tipo}"
        self._titulo(self.container, titulo)

        self._barra_botones(self.mostrar_menu_productos,
                            lambda: self._guardar_producto(modo, tipo_prod, prod_id),
                            f"💾  Guardar {label_tipo}")
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
        if es_pf:
            campos.extend([
                ("porcion_g",     "Porción (g, ej: 25):"),
                ("gramaje_g",     "Gramaje empaque (g, ej: 200):"),
                ("meses_caducidad", "Meses caducidad (opcional):"),
            ])

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
            if "porcion_g" in self._prod_entries:
                self._prod_entries["porcion_g"].delete(0, tk.END)
                self._prod_entries["porcion_g"].insert(0, str(p.porcion_g))
            if "gramaje_g" in self._prod_entries:
                self._prod_entries["gramaje_g"].delete(0, tk.END)
                self._prod_entries["gramaje_g"].insert(0, str(p.gramaje_g))
            if "meses_caducidad" in self._prod_entries:
                self._prod_entries["meses_caducidad"].delete(0, tk.END)
                if p.meses_caducidad is not None:
                    self._prod_entries["meses_caducidad"].insert(0, str(p.meses_caducidad))
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

    def _guardar_producto(self, modo, tipo_prod, prod_id):
        try:
            nombre = self._prod_entries["nombre"].get().strip()
            desc = self._prod_entries["descripcion"].get().strip()
            h_str = self._prod_entries["humedad_final"].get().strip().replace(",", ".")
            critico = self._critico_var.get()

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

            es_pf = (tipo_prod == "producto_final")
            porcion_g = 25.0
            gramaje_g = 200.0
            meses_cad = None
            if es_pf:
                p_str = self._prod_entries.get("porcion_g")
                g_str = self._prod_entries.get("gramaje_g")
                mc_str = self._prod_entries.get("meses_caducidad")
                if p_str:
                    porcion_g = float(p_str.get().strip().replace(",", ".") or "25")
                if g_str:
                    gramaje_g = float(g_str.get().strip().replace(",", ".") or "200")
                if mc_str:
                    mc_val = mc_str.get().strip()
                    meses_cad = int(mc_val) if mc_val else None

            with Session(engine) as s:
                if modo == "crear":
                    p = Producto(nombre=nombre, descripcion=desc, tipo=tipo_prod,
                                humedad_final=humedad_f, critico=critico,
                                porcion_g=porcion_g, gramaje_g=gramaje_g,
                                meses_caducidad=meses_cad)
                    s.add(p)
                    s.flush()
                else:
                    p = s.get(Producto, prod_id)
                    p.nombre = nombre
                    p.descripcion = desc
                    p.humedad_final = humedad_f
                    p.critico = critico
                    p.porcion_g = porcion_g
                    p.gramaje_g = gramaje_g
                    p.meses_caducidad = meses_cad
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

                # Caducidad
                cad_info = None
                fecha_est = p_l.fecha_caducidad_estimada()
                prox = p_l.ingredientes_proximos_a_caducar(5)
                if fecha_est or prox:
                    cad_info = {
                        "fecha_estimada": str(fecha_est) if fecha_est else None,
                        "proximos": [(ing.nombre, str(f)) for ing, f in prox],
                    }

                s.commit()

            messagebox.showinfo("✅ Guardado", f"Producto '{nombre_p}' guardado correctamente.")
            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre_p}",
                nombre_p, tabla_100g, tabla_p,
                porcion_final, merma_pct, factor, costo_kg,
                critico=critico_p, critico_auto=critico_auto,
                humedad_final_pct=humedad_pct, micronutrientes=micros,
                caducidad_info=cad_info)
            self.mostrar_menu_productos()

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

                fecha_est = p.fecha_caducidad_estimada()
                prox = p.ingredientes_proximos_a_caducar(5)
                cad_info = None
                if fecha_est or prox:
                    cad_info = {
                        "fecha_estimada": str(fecha_est) if fecha_est else None,
                        "proximos": [(ing.nombre, str(f)) for ing, f in prox],
                    }

            self._mostrar_toplevel_nutricional(
                f"Tabla Nutricional — {nombre}",
                nombre, tabla_100g, tabla_p, porcion_g, merma_pct, factor, costo,
                critico=critico, critico_auto=critico_auto,
                humedad_final_pct=humedad_pct, micronutrientes=micros,
                caducidad_info=cad_info)
            self.mostrar_menu_productos()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def mostrar_vista_eliminar_prod(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Eliminar Producto")

        fb = tk.Frame(self.container, bg=COLOR_BG)
        fb.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(fb, text="🔍  Buscar Producto a eliminar:",
                 font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        self._prod_combo_elim = self._crear_combobox_producto(fb, self._prod_seleccionar_elim)
        self._prod_combo_elim.pack(fill="x", pady=4)

        fbot = tk.Frame(self.container, bg=COLOR_BG)
        fbot.pack(fill="x", padx=20, pady=(4, 0))
        self._boton(fbot, "← Volver", self.mostrar_menu_productos, ancho=14).pack(side="left")
        self._boton(fbot, "🗑️  Eliminar", self._prod_eliminar,
                    color_bg=COLOR_PELIGRO, color_fg="white", ancho=16).pack(side="right")
        self._separador(self.container)

        self._prod_lbl_adv = tk.Label(
            self.container, text="Selecciona un Producto para eliminarlo.",
            fg="#757575", font=FONT_NORMAL, bg=COLOR_BG, wraplength=480, justify="center")
        self._prod_lbl_adv.pack(pady=30)
        self._prod_id_elim: int | None = None

    def _prod_seleccionar_elim(self, event=None):
        nombre = self._prod_combo_elim.get()
        if not nombre or nombre not in self.mapa_productos:
            return
        self._prod_id_elim = self.mapa_productos[nombre]
        self._prod_lbl_adv.config(
            text=f"⚠️  ¿Eliminar Producto?\n\n«{nombre}»\n\nEsta acción no se puede deshacer.",
            fg=COLOR_PELIGRO, font=("Segoe UI", 10, "bold"))

    def _prod_eliminar(self):
        if not self._prod_id_elim:
            messagebox.showerror("Sin selección", "Selecciona un Producto primero.")
            return
        if not messagebox.askyesno("Confirmar",
                                   "¿Eliminar este Producto?\n\nEsta acción es irreversible."):
            return
        try:
            with Session(engine) as s:
                p = s.get(Producto, self._prod_id_elim)
                if p:
                    s.delete(p)
                    s.commit()
            messagebox.showinfo("✅ Eliminado", "Producto eliminado correctamente.")
            self.mostrar_menu_productos()
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
                      "nutricional de un Producto.\n\n"
                      "Para agregar una nueva normativa, contacte al desarrollador.",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575",
                 justify="center", wraplength=500).pack(pady=16)

        self._boton(self.container, "← Volver al Menú Principal",
                    self.mostrar_menu_principal, ancho=30).pack(pady=10)