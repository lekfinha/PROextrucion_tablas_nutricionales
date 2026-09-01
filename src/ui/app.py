import tkinter as tk
from tkinter import ttk, messagebox
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.database import engine
from src.models.ingrediente import Ingrediente

# ──────────────────────────────────────────────────────────────────────────────
# Paleta de colores y estilos globales
# ──────────────────────────────────────────────────────────────────────────────
COLOR_BG        = "#F5F5F5"
COLOR_ACENTO    = "#2C7BE5"
COLOR_PELIGRO   = "#E53935"
COLOR_EXITO     = "#43A047"
COLOR_TEXTO     = "#212121"
FONT_TITULO     = ("Segoe UI", 15, "bold")
FONT_SUBTITULO  = ("Segoe UI", 11, "bold")
FONT_NORMAL     = ("Segoe UI", 10)
FONT_PEQUEÑA    = ("Segoe UI", 9)


class AppNutricion(tk.Tk):
    """Aplicación principal — Gestor de Ingredientes Pro Extrusion."""

    def __init__(self):
        super().__init__()
        self.title("Gestor de Ingredientes — Pro Extrusion")
        self.geometry("560x720")
        self.minsize(480, 600)
        self.config(bg=COLOR_BG)
        self.resizable(True, True)

        # Definición de campos: clave → (etiqueta, tipo_dato)
        self.campos_formulario = {
            "nombre":                   ("Nombre del Ingrediente",        str),
            "fabricante":               ("Fabricante / Proveedor",        str),
            "costo_kg":                 ("Costo por Kg ($)",              float),
            "energia_kcal":             ("Energía (Kcal/100g)",           float),
            "proteinas_g":              ("Proteínas (g/100g)",            float),
            "grasa_total_g":            ("Grasa Total (g)",               float),
            "grasa_saturada_g":         ("  └ Grasa Saturada (g)",        float),
            "grasa_monoinsaturada_g":   ("  └ Grasa Monoinsat. (g)",      float),
            "grasa_poliinsaturada_g":   ("  └ Grasa Poliinsat. (g)",      float),
            "acidos_grasos_trans_g":    ("  └ Ácidos Grasos Trans (g)",   float),
            "colesterol_mg":            ("Colesterol (mg)",               float),
            "carbohidratos_disp_g":     ("H. de Carbono Disp. (g)",       float),
            "azucares_totales_g":       ("  └ Azúcares Totales (g)",      float),
            "sorbitol_g":               ("  └ Sorbitol (g)",              float),
            "maltitol_g":              ("  └ Maltitol (g)",              float),
            "fibra_dietetica_g":        ("Fibra Dietética (g)",           float),
            "fibra_soluble_g":          ("  └ Fibra Soluble (g)",         float),
            "fibra_insoluble_g":        ("  └ Fibra Insoluble (g)",       float),
            "sodio_mg":                 ("Sodio (mg)",                    float),
            "humedad_porcentaje":       ("Humedad (%)",                   float),
        }

        self.entries: dict[str, tk.Entry] = {}
        self.mapa_ingredientes: dict[str, int] = {}   # id_unico → id
        self.ingrediente_actual_id: int | None = None

        # Contenedor principal que ocupa toda la ventana
        self.container = tk.Frame(self, bg=COLOR_BG)
        self.container.pack(fill="both", expand=True)

        self.mostrar_menu_principal()

    # ── Utilidades de navegación ───────────────────────────────────────────────

    def limpiar_pantalla(self):
        """Destruye todos los widgets del contenedor."""
        for widget in self.container.winfo_children():
            widget.destroy()
        self.entries.clear()
        self.ingrediente_actual_id = None

    def _titulo(self, parent: tk.Widget, texto: str) -> tk.Label:
        lbl = tk.Label(parent, text=texto, font=FONT_TITULO,
                       bg=COLOR_BG, fg=COLOR_TEXTO)
        lbl.pack(pady=(20, 10))
        return lbl

    def _boton(self, parent: tk.Widget, texto: str, comando,
               color_bg: str = "#E0E0E0", color_fg: str = COLOR_TEXTO,
               ancho: int = 28) -> tk.Button:
        return tk.Button(
            parent, text=texto, command=comando,
            bg=color_bg, fg=color_fg, font=FONT_NORMAL,
            width=ancho, relief="flat", cursor="hand2",
            activebackground=color_bg, activeforeground=color_fg,
            pady=6,
        )

    # ── Combobox con búsqueda en tiempo real ───────────────────────────────────

    def _recargar_mapa_ingredientes(self):
        """Carga desde BD el mapa nombre_único → id."""
        with Session(engine) as session:
            ingredientes = session.query(Ingrediente).order_by(Ingrediente.nombre).all()
            self.mapa_ingredientes = {ing.id_unico: ing.id for ing in ingredientes}

    def _crear_combobox_buscable(self, parent: tk.Widget,
                                  callback_seleccion) -> ttk.Combobox:
        """
        Crea un Combobox editable que filtra opciones al escribir.
        Al seleccionar una opción llama a callback_seleccion(event).
        """
        self._recargar_mapa_ingredientes()
        opciones_completas = sorted(self.mapa_ingredientes.keys())

        var = tk.StringVar()
        combo = ttk.Combobox(parent, textvariable=var, width=48,
                             font=FONT_NORMAL)
        combo['values'] = opciones_completas

        def _on_keyrelease(event):
            # Teclas de navegación no deben filtrar
            if event.keysym in ("Down", "Up", "Return", "Escape"):
                return
            texto = var.get().lower().strip()
            if texto == "":
                combo['values'] = opciones_completas
            else:
                filtradas = [o for o in opciones_completas
                             if texto in o.lower()]
                combo['values'] = filtradas
            # Abre el dropdown si hay resultados
            if combo['values']:
                combo.event_generate('<Down>')

        combo.bind('<KeyRelease>', _on_keyrelease)
        combo.bind('<<ComboboxSelected>>', callback_seleccion)
        return combo

    # ── Menú Principal ─────────────────────────────────────────────────────────

    def mostrar_menu_principal(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Menú Principal")

        tk.Label(self.container,
                 text="Sistema de Gestión Nutricional — Pro Extrusion",
                 font=FONT_PEQUEÑA, bg=COLOR_BG, fg="#757575").pack(pady=(0, 20))

        frame_botones = tk.Frame(self.container, bg=COLOR_BG)
        frame_botones.pack()

        self._boton(frame_botones, "➕  Agregar Ingrediente",
                    self.mostrar_menu_agregar,
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=8)
        self._boton(frame_botones, "✏️  Modificar Ingrediente",
                    lambda: self.mostrar_formulario("modificar")).pack(pady=8)
        self._boton(frame_botones, "🗑️  Eliminar Ingrediente",
                    self.mostrar_vista_eliminar,
                    color_bg=COLOR_PELIGRO, color_fg="white").pack(pady=8)

    # ── Menú Agregar ───────────────────────────────────────────────────────────

    def mostrar_menu_agregar(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Agregar Ingrediente")

        frame_botones = tk.Frame(self.container, bg=COLOR_BG)
        frame_botones.pack(pady=10)

        self._boton(frame_botones, "📄  Crear ingrediente desde cero",
                    lambda: self.mostrar_formulario("crear_nuevo"),
                    color_bg=COLOR_ACENTO, color_fg="white").pack(pady=8)
        self._boton(frame_botones, "📋  Crear a partir de uno existente",
                    lambda: self.mostrar_formulario("crear_desde_existente")).pack(pady=8)

        tk.Frame(self.container, bg="#BDBDBD", height=1).pack(
            fill="x", padx=40, pady=20)

        self._boton(self.container, "← Volver al Menú Principal",
                    self.mostrar_menu_principal,
                    ancho=30).pack()

    # ── Formulario CRUD (crear / clonar / modificar) ──────────────────────────

    def mostrar_formulario(self, modo: str):
        self.limpiar_pantalla()

        titulos = {
            "crear_nuevo":           "Nuevo Ingrediente",
            "crear_desde_existente": "Clonar Ingrediente",
            "modificar":             "Modificar Ingrediente",
        }
        self._titulo(self.container, titulos[modo])

        # ── Buscador (solo en modos que lo requieren) ──
        if modo in ("crear_desde_existente", "modificar"):
            frame_busq = tk.Frame(self.container, bg=COLOR_BG)
            frame_busq.pack(fill="x", padx=20, pady=(0, 6))
            tk.Label(frame_busq, text="🔍  Buscar ingrediente existente:",
                     font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
            self.combo_busqueda = self._crear_combobox_buscable(
                frame_busq, self.cargar_datos_en_formulario)
            self.combo_busqueda.pack(fill="x", pady=4)

        # ── Barra de botones: va ANTES del canvas para que expand=True no la tape ──
        destino_volver = (
            self.mostrar_menu_agregar
            if modo in ("crear_nuevo", "crear_desde_existente")
            else self.mostrar_menu_principal
        )
        frame_botones = tk.Frame(self.container, bg=COLOR_BG)
        frame_botones.pack(fill="x", padx=20, pady=(4, 0))

        self._boton(frame_botones, "← Volver",
                    destino_volver, ancho=14).pack(side="left", padx=(0, 6))
        self._boton(frame_botones, "💾  Guardar Ingrediente",
                    lambda: self.guardar_ingrediente(modo),
                    color_bg=COLOR_EXITO, color_fg="white",
                    ancho=22).pack(side="right")

        # Separador visual
        tk.Frame(self.container, bg="#BDBDBD", height=1).pack(
            fill="x", padx=20, pady=6)

        # ── Área scrollable con los campos del formulario ──
        frame_scroll_outer = tk.Frame(self.container, bg=COLOR_BG)
        frame_scroll_outer.pack(fill="both", expand=True, padx=20)

        canvas = tk.Canvas(frame_scroll_outer, bg=COLOR_BG,
                           highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_scroll_outer,
                                  orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame_form = tk.Frame(canvas, bg=COLOR_BG)
        window_id = canvas.create_window((0, 0), window=frame_form, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(window_id, width=event.width)

        frame_form.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Scroll con rueda del ratón
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>",
                        lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>",
                        lambda e: canvas.yview_scroll(1, "units"))

        # Renderizar campos
        for key, (label_text, _) in self.campos_formulario.items():
            row = tk.Frame(frame_form, bg=COLOR_BG)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=label_text, font=FONT_NORMAL,
                     bg=COLOR_BG, fg=COLOR_TEXTO,
                     width=26, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=FONT_NORMAL, relief="solid", bd=1)
            entry.pack(side="right", expand=True, fill="x")
            self.entries[key] = entry



    # ── Vista Eliminar ────────────────────────────────────────────────────────

    def mostrar_vista_eliminar(self):
        self.limpiar_pantalla()
        self._titulo(self.container, "Eliminar Ingrediente")

        # ── Buscador ──
        frame_busq = tk.Frame(self.container, bg=COLOR_BG)
        frame_busq.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(frame_busq, text="🔍  Buscar ingrediente a eliminar:",
                 font=FONT_PEQUEÑA, bg=COLOR_BG).pack(anchor="w")
        self.combo_busqueda = self._crear_combobox_buscable(
            frame_busq, self.seleccionar_para_eliminar)
        self.combo_busqueda.pack(fill="x", pady=4)

        # ── Botones (misma posición que en el formulario que sí funciona) ──
        frame_botones = tk.Frame(self.container, bg=COLOR_BG)
        frame_botones.pack(fill="x", padx=20, pady=(4, 0))

        self._boton(frame_botones, "← Volver",
                    self.mostrar_menu_principal,
                    ancho=14).pack(side="left", padx=(0, 6))
        self._boton(frame_botones, "🗑️  Eliminar",
                    self.eliminar_ingrediente,
                    color_bg=COLOR_PELIGRO, color_fg="white",
                    ancho=16).pack(side="right")

        # Separador visual
        tk.Frame(self.container, bg="#BDBDBD", height=1).pack(
            fill="x", padx=20, pady=6)

        # ── Etiqueta de advertencia (se actualiza al seleccionar) ──
        self.lbl_advertencia = tk.Label(
            self.container, text="Selecciona un ingrediente para eliminarlo.",
            fg="#757575", font=FONT_NORMAL, bg=COLOR_BG,
            wraplength=480, justify="center")
        self.lbl_advertencia.pack(pady=30)


    # ── Lógica de BD ──────────────────────────────────────────────────────────

    def cargar_datos_en_formulario(self, event=None):
        """Carga los valores del ingrediente seleccionado en los entries."""
        seleccion = self.combo_busqueda.get()
        if not seleccion or seleccion not in self.mapa_ingredientes:
            return
        self.ingrediente_actual_id = self.mapa_ingredientes[seleccion]
        with Session(engine) as session:
            ing = session.get(Ingrediente, self.ingrediente_actual_id)
            if ing is None:
                return
            for key, entry in self.entries.items():
                entry.delete(0, tk.END)
                entry.insert(0, str(getattr(ing, key)))

    def guardar_ingrediente(self, modo: str):
        """Valida el formulario y persiste el ingrediente en la BD."""
        try:
            datos: dict = {}
            for key, (label_text, tipo_dato) in self.campos_formulario.items():
                valor_str = self.entries[key].get().strip()

                if not valor_str:
                    if tipo_dato is str:
                        raise ValueError(
                            f"El campo '{label_text}' no puede estar vacío.")
                    valor_str = "0.0"

                if tipo_dato is float:
                    valor_str = valor_str.replace(",", ".")

                datos[key] = tipo_dato(valor_str)

            with Session(engine) as session:
                if modo == "modificar":
                    if not self.ingrediente_actual_id:
                        raise ValueError(
                            "Debes seleccionar un ingrediente para modificar.")
                    ing = session.get(Ingrediente, self.ingrediente_actual_id)
                    for k, v in datos.items():
                        setattr(ing, k, v)
                else:
                    # crear_nuevo y crear_desde_existente → nuevo registro
                    session.add(Ingrediente(**datos))

                session.commit()

            messagebox.showinfo("✅ Éxito", "Ingrediente guardado correctamente.")
            self.mostrar_menu_principal()

        except ValueError as exc:
            messagebox.showerror("Error de validación", str(exc))
        except IntegrityError:
            messagebox.showerror(
                "Duplicado",
                "Ya existe un ingrediente con ese nombre y fabricante.")
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))

    def seleccionar_para_eliminar(self, event=None):
        """Actualiza la etiqueta de advertencia al seleccionar un ingrediente."""
        seleccion = self.combo_busqueda.get()
        if not seleccion or seleccion not in self.mapa_ingredientes:
            return
        self.ingrediente_actual_id = self.mapa_ingredientes[seleccion]
        self.lbl_advertencia.config(
            text=f"⚠️  ¿Estás seguro de eliminar?\n\n«{seleccion}»\n\nEsta acción no se puede deshacer.",
            fg=COLOR_PELIGRO,
            font=("Segoe UI", 10, "bold"))


    def eliminar_ingrediente(self):
        """Elimina el ingrediente seleccionado tras confirmar."""
        if not self.ingrediente_actual_id:
            messagebox.showerror(
                "Sin selección",
                "Primero debes buscar y seleccionar un ingrediente.")
            return
        if not messagebox.askyesno(
            "Confirmar eliminación",
            "¿Estás absolutamente seguro?\n\nEsta acción es irreversible."
        ):
            return
        try:
            with Session(engine) as session:
                ing = session.get(Ingrediente, self.ingrediente_actual_id)
                if ing:
                    session.delete(ing)
                    session.commit()
            messagebox.showinfo("✅ Eliminado",
                                "Ingrediente eliminado correctamente.")
            self.mostrar_menu_principal()
        except Exception as exc:
            messagebox.showerror("Error inesperado", str(exc))