import os
import math
import json
import csv

import cv2
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from openpyxl import Workbook

# ---------------- GLOBALS ----------------
SETTINGS_FILE = "grid_settings.json"

image_paths = []          # original file paths
processed_images = []     # PIL images with grid
point_positions_list = [] # list[list[(x,y)]]
point_values_list = []    # list[list[float]]
tree_items = []           # one tree item id per image (or None if deleted)
thumb_buttons = []        # list of thumbnail buttons

thumb_photo_refs = []     # keep references for thumbnails

# ---------------- SETTINGS ----------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)


# ---------------- IMAGE HELPERS ----------------
def make_square(img_cv):
    """Center-crop to square."""
    h, w = img_cv.shape[:2]
    size = min(h, w)
    cx, cy = w // 2, h // 2
    return img_cv[cy - size // 2:cy + size // 2,
                  cx - size // 2:cx + size // 2]


def draw_grid_cv(img_cv, rows, cols, color=(0, 255, 0), thickness=1):
    """
    Draw grid AND return counting points.
    - rows, cols: number of intersections in vertical/horizontal.
    - Grid lines are evenly spaced inside the image (no border lines used as intersections).
    - Counting points are at grid intersections: rows * cols points, all inside (no border points).
    """
    img_copy = img_cv.copy()
    h, w = img_copy.shape[:2]

    if rows < 1 or cols < 1:
        return img_copy, []

    # We place rows and cols internal lines, spaced using (rows+1) and (cols+1)
    # so that all intersections are inside and not on borders.
    cell_h = h / (rows + 1)
    cell_w = w / (cols + 1)

    # Draw internal grid lines (do not draw at borders)
    for r in range(1, rows + 1):
        y = int(round(r * cell_h))
        cv2.line(img_copy, (0, y), (w, y), color, thickness)

    for c in range(1, cols + 1):
        x = int(round(c * cell_w))
        cv2.line(img_copy, (x, 0), (x, h), color, thickness)

    # Counting points at intersections of these internal lines
    point_positions = []
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            x = int(round(c * cell_w))
            y = int(round(r * cell_h))
            point_positions.append((x, y))

    return img_copy, point_positions


def cv2_to_pil(cv_img):
    cv_img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cv_img_rgb)


# ---------------- EXPORT HELPERS ----------------
def create_pages(images, output_dir, images_per_page=4, export_as_pdf=False):
    if not images:
        return

    a4_width, a4_height = 2480, 3508
    pages = []

    cols = 2
    rows = math.ceil(images_per_page / cols)
    spacing = 40
    square_size = min(
        (a4_width - (cols + 1) * spacing) // cols,
        (a4_height - (rows + 1) * spacing) // rows,
    )
    total_pages = math.ceil(len(images) / images_per_page)

    for page_num in range(total_pages):
        page = Image.new("RGB", (a4_width, a4_height), (255, 255, 255))
        draw = ImageDraw.Draw(page)

        for i in range(images_per_page):
            idx = page_num * images_per_page + i
            if idx >= len(images):
                break

            img = images[idx].resize((square_size, square_size))
            col = i % cols
            row = i // cols
            x = spacing + col * (square_size + spacing)
            y = spacing + row * (square_size + spacing)
            page.paste(img, (x, y))

        # Page number
        font_size = 48
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = f"Page {page_num + 1}"
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((a4_width - tw - 60, a4_height - th - 40),
                  text, fill=(0, 0, 0), font=font)

        pages.append(page)

    if export_as_pdf:
        pdf_path = os.path.join(output_dir, "output.pdf")
        c = pdf_canvas.Canvas(pdf_path, pagesize=A4)
        for i, p in enumerate(pages):
            tmp_path = os.path.join(output_dir, f"_temp_page_{i+1}.jpg")
            p.save(tmp_path)
            c.drawImage(tmp_path, 0, 0, width=A4[0], height=A4[1])
            c.showPage()
            os.remove(tmp_path)
        c.save()
    else:
        for i, p in enumerate(pages):
            p.save(os.path.join(output_dir, f"grid_page_{i+1}.jpg"))

    messagebox.showinfo("Export", f"{len(pages)} page(s) exported to:\n{output_dir}")


def export_results_to_csv(output_dir):
    valid_items = [it for it in tree_items if it is not None]
    if not valid_items:
        messagebox.showerror("Error", "No results to export.")
        return

    csv_path = os.path.join(output_dir, "astm_e562_results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["S.No", "Image", "Volume %"])
        serial = 1
        for item_id in tree_items:
            if item_id is None:
                continue
            values = outputs_tree.item(item_id, "values")
            writer.writerow([serial, values[0], values[1]])
            serial += 1

    messagebox.showinfo("Export", f"Results saved to:\n{csv_path}")


def export_results_to_excel(output_dir):
    valid_items = [it for it in tree_items if it is not None]
    if not valid_items:
        messagebox.showerror("Error", "No results to export.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "ASTM_E562"

    ws.append(["S.No", "Image", "Volume %"])
    serial = 1
    for item_id in tree_items:
        if item_id is None:
            continue
        values = outputs_tree.item(item_id, "values")
        ws.append([serial, values[0], values[1]])
        serial += 1

    xlsx_path = os.path.join(output_dir, "astm_e562_results.xlsx")
    wb.save(xlsx_path)

    messagebox.showinfo("Export", f"Excel file saved to:\n{xlsx_path}")


# ---------------- POINT COUNT LOGIC ----------------
def calculate_percentage_for_image(img_index):
    if not (0 <= img_index < len(point_values_list)):
        messagebox.showerror("Error", "Invalid image index.")
        return

    values = point_values_list[img_index]
    total_points = len(values)
    if total_points == 0:
        messagebox.showerror("Error", "No points for this image.")
        return

    s = sum(values)
    percent = (s / total_points) * 100.0

    # Update table only if row still exists
    if 0 <= img_index < len(tree_items):
        item_id = tree_items[img_index]
        if item_id is not None:
            outputs_tree.set(item_id, "percent", f"{percent:.2f}")

    update_progress_ui()

    img_name = ""
    if img_index < len(image_paths):
        img_name = os.path.basename(image_paths[img_index])

    messagebox.showinfo(
        "ASTM E562",
        f"Image: {img_name}\n"
        f"Counting points: {total_points}\n"
        f"Weighted sum: {s:.2f}\n"
        f"Volume fraction: {percent:.2f} %",
    )


def handle_point_click(event, win):
    canvas = win.canvas
    x_click, y_click = event.x, event.y

    positions = win.point_positions
    circles = win.point_circles
    img_index = win.img_index
    values = point_values_list[img_index]

    # Find nearest counting point
    min_dist = 1e9
    idx = None
    for i, (px, py) in enumerate(positions):
        d = (px - x_click) ** 2 + (py - y_click) ** 2
        if d < min_dist:
            min_dist = d
            idx = i

    if idx is None:
        return

    # Popup for classification
    popup = tk.Toplevel(win)
    popup.title("Point type")

    tk.Label(popup, text="Select point classification:").pack(pady=4, padx=8)

    def set_inside():
        values[idx] = 1.0
        canvas.itemconfig(circles[idx], fill="green")
        popup.destroy()

    def set_boundary():
        values[idx] = 0.5
        canvas.itemconfig(circles[idx], fill="orange")
        popup.destroy()

    def reset_point():
        values[idx] = 0.0
        canvas.itemconfig(circles[idx], fill="gray")
        popup.destroy()

    tk.Button(popup, text="Inside (1.0)",
              bg="green", fg="white", command=set_inside).pack(fill="x", padx=8, pady=2)
    tk.Button(popup, text="Boundary (0.5)",
              bg="orange", fg="white", command=set_boundary).pack(fill="x", padx=8, pady=2)
    tk.Button(popup, text="Reset",
              command=reset_point).pack(fill="x", padx=8, pady=4)


def open_point_selection(img_index):
    """Open counting window for given image index."""
    if not (0 <= img_index < len(processed_images)):
        return

    pil_img = processed_images[img_index]
    positions = point_positions_list[img_index]
    values = point_values_list[img_index]

    win = tk.Toplevel(root)
    
    img_name = ""
    if img_index < len(image_paths):
        img_name = os.path.basename(image_paths[img_index])
        
    win.title(f"Point selection – {img_name}")

    canvas = tk.Canvas(win, width=pil_img.width, height=pil_img.height)
    canvas.pack()

    tk_img = ImageTk.PhotoImage(pil_img)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)
    canvas.image_ref = tk_img

    win.canvas = canvas
    win.point_positions = positions
    win.img_index = img_index
    win.point_circles = []

    for i, (x, y) in enumerate(positions):
        v = values[i]
        if v == 1.0:
            color = "green"
        elif v == 0.5:
            color = "orange"
        else:
            color = "gray"
        circle = canvas.create_oval(x - 4, y - 4, x + 4, y + 4,
                                    fill=color, outline="")
        win.point_circles.append(circle)

    canvas.bind("<Button-1>", lambda e, w=win: handle_point_click(e, w))

    tk.Button(
        win,
        text="Calculate %",
        command=lambda idx=img_index: calculate_percentage_for_image(idx)
    ).pack(pady=6)


# ---------------- MAIN UI LOGIC ----------------
def update_progress_ui():
    total = len(processed_images)
    if total == 0:
        progress_label.configure(text="Processed: 0 / 0")
        return

    done_count = 0
    for i in range(total):
        is_done = False
        if i < len(tree_items) and tree_items[i] is not None:
            val = outputs_tree.item(tree_items[i], "values")
            if len(val) > 1 and val[1] != "":
                is_done = True
                done_count += 1
                
        if i < len(thumb_buttons):
            if is_done:
                thumb_buttons[i].configure(border_width=2, border_color="#4caf50") # Green
            else:
                thumb_buttons[i].configure(border_width=2, border_color="#f44336") # Red
                
        if i < len(tree_items) and tree_items[i] is not None:
            if is_done:
                outputs_tree.item(tree_items[i], tags=("done",))
            else:
                outputs_tree.item(tree_items[i], tags=("not_done",))
                
    progress_label.configure(text=f"Processed: {done_count} / {total}")


def refresh_main_preview(index=0):
    """Show selected image in big preview on left."""
    if not processed_images:
        main_image_label.configure(image=None, text="No image loaded", compound="center")
        main_image_label.image = None
        main_image_label.current_index = None
        return

    index = max(0, min(len(processed_images) - 1, index))
    pil_img = processed_images[index]

    max_w, max_h = 600, 450
    w, h = pil_img.size
    scale = min(max_w / w, max_h / h, 1.0)
    new_size = (int(w * scale), int(h * scale))
    resized = pil_img.resize(new_size, Image.LANCZOS)

    photo = ImageTk.PhotoImage(resized)
    
    img_name = ""
    if index < len(image_paths):
        img_name = os.path.basename(image_paths[index])

    main_image_label.configure(image=photo, text=img_name, compound="bottom", font=("", 14, "bold"))
    main_image_label.image = photo
    main_image_label.current_index = index


def build_thumbnails():
    """Thumbnail bar from processed_images."""
    global thumb_buttons
    for widget in thumb_inner_frame.winfo_children():
        widget.destroy()
    thumb_photo_refs.clear()
    thumb_buttons.clear()

    for i, img in enumerate(processed_images):
        thumb = img.resize((80, 80), Image.LANCZOS)
        photo = ImageTk.PhotoImage(thumb)
        thumb_photo_refs.append(photo)

        btn = ctk.CTkButton(
            thumb_inner_frame,
            image=photo,
            text="",
            width=80,
            height=80,
            fg_color="transparent",
            hover_color="#333333",
            border_width=2,
            border_color="#f44336",
            command=lambda idx=i: on_thumbnail_click(idx),
        )
        btn.grid(row=0, column=i, padx=4, pady=4)
        thumb_buttons.append(btn)

    thumb_canvas.update_idletasks()
    thumb_canvas.configure(scrollregion=thumb_canvas.bbox("all"))
    update_progress_ui()


def on_thumbnail_click(idx):
    refresh_main_preview(idx)


def process_images():
    """Apply grid to all selected images."""
    global processed_images, point_positions_list, point_values_list, tree_items

    try:
        rows = int(row_var.get())
        cols = int(col_var.get())
    except ValueError:
        messagebox.showerror("Error", "Enter valid integer values for lines.")
        return

    if rows < 1 or cols < 1:
        messagebox.showerror("Error", "Rows and cols must be >= 1.")
        return

    total_points = rows * cols
    inter_label_var.set(f"Counting points per image: {total_points} ( {rows} x {cols} )")

    color_str = color_var.get()
    if color_str:
        grid_color_bgr = tuple(int(c) for c in reversed(eval(color_str)))
    else:
        grid_color_bgr = (0, 255, 0)

    processed_images.clear()
    point_positions_list.clear()
    point_values_list.clear()
    tree_items.clear()
    outputs_tree.delete(*outputs_tree.get_children())

    for path in image_paths:
        img_cv = cv2.imread(path)
        if img_cv is None:
            continue
        img_square = make_square(img_cv)
        img_with_grid, pts = draw_grid_cv(img_square, rows, cols, color=grid_color_bgr)
        pil_img = cv2_to_pil(img_with_grid)

        processed_images.append(pil_img)
        point_positions_list.append(pts)

        fname = os.path.basename(path)
        mode = calc_mode_var.get()
        
        if mode == "Manual":
            initial_values = [0.0] * len(pts)
            item_id = outputs_tree.insert("", "end", values=(fname, ""))
        else:
            gray = cv2.cvtColor(img_square, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Create a boundary mask
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            boundary_mask = cv2.morphologyEx(thresh, cv2.MORPH_GRADIENT, kernel)
            
            initial_values = []
            for (x, y) in pts:
                if 0 <= y < thresh.shape[0] and 0 <= x < thresh.shape[1]:
                    if boundary_mask[y, x] > 0:
                        initial_values.append(0.5)
                    else:
                        val = thresh[y, x]
                        if mode == "Auto (Dark Phase)":
                            initial_values.append(1.0 if val == 0 else 0.0)
                        else:
                            initial_values.append(1.0 if val == 255 else 0.0)
                else:
                    initial_values.append(0.0)
                    
            s = sum(initial_values)
            percent = (s / len(pts)) * 100.0 if len(pts) > 0 else 0.0
            item_id = outputs_tree.insert("", "end", values=(fname, f"{percent:.2f}"))

        point_values_list.append(initial_values)
        tree_items.append(item_id)

    if not processed_images:
        messagebox.showerror("Error", "No valid images processed.")
        return

    build_thumbnails()
    refresh_main_preview(0)

    save_settings({
        "rows": row_var.get(),
        "cols": col_var.get(),
        "color": color_var.get(),
        "calc_mode": calc_mode_var.get(),
    })


def select_images():
    global image_paths
    files = filedialog.askopenfilenames(
        title="Select Microstructure Images",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.bmp"), ("All files", "*.*")]
    )
    if not files:
        return
    image_paths = list(files)
    process_images()


def pick_color():
    c = colorchooser.askcolor(title="Choose grid color")[0]
    if c:
        color_var.set(str(c))


def open_point_selection_for_current(event=None):
    idx = getattr(main_image_label, "current_index", None)

    # If no image yet → open file selector directly
    if idx is None or not processed_images:
        files = filedialog.askopenfilenames(
            title="Select Microstructure Images",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.bmp"), ("All files", "*.*")]
        )
        if files:
            global image_paths
            image_paths = list(files)
            process_images()
        return

    # If image exists → open point selection window
    open_point_selection(idx)



def calculate_current_image():
    idx = getattr(main_image_label, "current_index", None)
    if idx is None:
        messagebox.showerror("Error", "No image selected.")
        return
    calculate_percentage_for_image(idx)


def export_images_jpg_clicked():
    if not processed_images:
        messagebox.showerror("Error", "No processed images to export.")
        return
    out_dir = filedialog.askdirectory(title="Select export folder")
    if not out_dir:
        return
    try:
        per_page = int(images_per_page_var.get())
    except ValueError:
        per_page = 4
    create_pages(processed_images, out_dir, per_page, export_as_pdf=False)


def export_images_pdf_clicked():
    if not processed_images:
        messagebox.showerror("Error", "No processed images to export.")
        return
    out_dir = filedialog.askdirectory(title="Select export folder")
    if not out_dir:
        return
    try:
        per_page = int(images_per_page_var.get())
    except ValueError:
        per_page = 4
    create_pages(processed_images, out_dir, per_page, export_as_pdf=True)


def export_csv_clicked():
    if not tree_items:
        messagebox.showerror("Error", "No results to export.")
        return
    out_dir = filedialog.askdirectory(title="Select folder for CSV")
    if not out_dir:
        return
    export_results_to_csv(out_dir)


def export_excel_clicked():
    if not tree_items:
        messagebox.showerror("Error", "No results to export.")
        return
    out_dir = filedialog.askdirectory(title="Select folder for Excel")
    if not out_dir:
        return
    export_results_to_excel(out_dir)


def delete_selected_row():
    """Clear ONLY the percentage cell of the selected row."""
    sel = outputs_tree.selection()
    if not sel:
        messagebox.showerror("Error", "Select a row to clear.")
        return

    for item in sel:
        try:
            idx = tree_items.index(item)
        except ValueError:
            continue

        # Clear displayed percentage
        outputs_tree.set(item, "percent", "")

        # Reset all point values for that image
        point_values_list[idx] = [0.0] * len(point_values_list[idx])

        # Also refresh preview if user is on that image
        if main_image_label.current_index == idx:
            refresh_main_preview(idx)

    update_progress_ui()



# ---------------- BUILD UI ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("ASTM E562 – Grid & Point Counter")
root.geometry("1200x680")

root.grid_columnconfigure(0, weight=3)
root.grid_columnconfigure(1, weight=2)
root.grid_rowconfigure(0, weight=1)

# LEFT PANEL ------------------------------------------------------------
left_frame = ctk.CTkFrame(root)
left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
left_frame.grid_rowconfigure(0, weight=5)
left_frame.grid_rowconfigure(1, weight=1)
left_frame.grid_rowconfigure(2, weight=0)
left_frame.grid_rowconfigure(3, weight=0)
left_frame.grid_columnconfigure(0, weight=1)

# main image area (click to start point counter)
main_image_label = ctk.CTkLabel(
    left_frame,
    text="No image loaded",
    anchor="center",
    fg_color="#1f1f1f"
)
main_image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
main_image_label.current_index = None
main_image_label.bind("<Button-1>", open_point_selection_for_current)

# button under preview to calculate % for current image
calc_current_btn = ctk.CTkButton(
    left_frame, text="Calculate % (current image)", command=calculate_current_image
)
calc_current_btn.grid(row=1, column=0, pady=(0, 5))

# thumbnail strip
thumb_frame = ctk.CTkFrame(left_frame)
thumb_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 5))

thumb_canvas = tk.Canvas(thumb_frame, height=110, bg="#1f1f1f", highlightthickness=0)
thumb_scrollbar = tk.Scrollbar(thumb_frame, orient="horizontal", command=thumb_canvas.xview)
thumb_inner_frame = ctk.CTkFrame(thumb_canvas)

thumb_inner_id = thumb_canvas.create_window((0, 0), window=thumb_inner_frame, anchor="nw")
thumb_canvas.configure(xscrollcommand=thumb_scrollbar.set)

thumb_canvas.pack(fill="both", expand=True, side="top")
thumb_scrollbar.pack(fill="x", side="bottom")


def _on_thumb_config(event):
    thumb_canvas.configure(scrollregion=thumb_canvas.bbox("all"))


thumb_inner_frame.bind("<Configure>", _on_thumb_config)

# add image button
add_image_btn = ctk.CTkButton(
    left_frame,
    text="Add / Load Images",
    command=select_images
)
add_image_btn.grid(row=3, column=0, pady=(0, 10))

# RIGHT PANEL -----------------------------------------------------------
right_frame = ctk.CTkFrame(root)
right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
right_frame.grid_rowconfigure(0, weight=0)
right_frame.grid_rowconfigure(1, weight=1)
right_frame.grid_rowconfigure(2, weight=0)
right_frame.grid_columnconfigure(0, weight=1)

# --- Grid orientation section ---
grid_frame = ctk.CTkFrame(right_frame)
grid_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=10)
grid_frame.grid_columnconfigure(0, weight=1)
grid_frame.grid_columnconfigure(1, weight=1)
grid_frame.grid_columnconfigure(2, weight=1)

ctk.CTkLabel(grid_frame, text="Grid orientation").grid(row=0, column=0, columnspan=3, pady=(5, 5))

row_var = tk.StringVar()
col_var = tk.StringVar()
color_var = tk.StringVar()
calc_mode_var = tk.StringVar(value="Manual")
inter_label_var = tk.StringVar(value="Counting points per image: -")

ctk.CTkLabel(grid_frame, text="No. of cells (H, V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
row_entry = ctk.CTkEntry(grid_frame, textvariable=row_var, width=70)
row_entry.grid(row=1, column=1, padx=5)
col_entry = ctk.CTkEntry(grid_frame, textvariable=col_var, width=70)
col_entry.grid(row=1, column=2, padx=5)

inter_label = ctk.CTkLabel(grid_frame, textvariable=inter_label_var)
inter_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=2)

ctk.CTkLabel(grid_frame, text="Detection Mode:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
mode_menu = ctk.CTkOptionMenu(grid_frame, variable=calc_mode_var, values=["Manual", "Auto (Dark Phase)", "Auto (Light Phase)"])
mode_menu.grid(row=3, column=1, columnspan=2, padx=5, sticky="we")

pick_color_btn = ctk.CTkButton(grid_frame, text="Grid color", width=80, command=pick_color)
pick_color_btn.grid(row=4, column=0, padx=5, pady=5, sticky="w")

apply_btn = ctk.CTkButton(grid_frame, text="Apply grid", command=process_images)
apply_btn.grid(row=4, column=2, padx=5, pady=5, sticky="e")

# --- Outputs table section ---
outputs_frame = ctk.CTkFrame(right_frame)
outputs_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
outputs_frame.grid_rowconfigure(1, weight=1)
outputs_frame.grid_columnconfigure(0, weight=1)

outputs_header_frame = ctk.CTkFrame(outputs_frame, fg_color="transparent")
outputs_header_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=5)
outputs_header_frame.grid_columnconfigure(0, weight=1)
outputs_header_frame.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(outputs_header_frame, text="Outputs", font=("", 14, "bold")).grid(row=0, column=0, sticky="w")
progress_label = ctk.CTkLabel(outputs_header_frame, text="Processed: 0 / 0", text_color="#aaaaaa")
progress_label.grid(row=0, column=1, sticky="e")

columns = ("image", "percent")
outputs_tree = ttk.Treeview(outputs_frame, columns=columns, show="headings", height=8)
outputs_tree.tag_configure("done", foreground="#4caf50")
outputs_tree.tag_configure("not_done", foreground="#f44336")
outputs_tree.heading("image", text="Image")
outputs_tree.heading("percent", text="Percentage (%)")
outputs_tree.column("image", width=160, anchor="w")
outputs_tree.column("percent", width=100, anchor="center")

tree_scroll = ttk.Scrollbar(outputs_frame, orient="vertical", command=outputs_tree.yview)
outputs_tree.configure(yscrollcommand=tree_scroll.set)
outputs_tree.grid(row=1, column=0, sticky="nsew")
tree_scroll.grid(row=1, column=1, sticky="ns")

delete_row_btn = ctk.CTkButton(outputs_frame, text="Delete selected row", command=delete_selected_row)
delete_row_btn.grid(row=2, column=0, pady=5, sticky="w", padx=5)

# --- Exports section ---
export_frame = ctk.CTkFrame(right_frame)
export_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
export_frame.grid_columnconfigure(0, weight=1)
export_frame.grid_columnconfigure(1, weight=1)
export_frame.grid_columnconfigure(2, weight=1)
export_frame.grid_columnconfigure(3, weight=1)

ctk.CTkLabel(export_frame, text="Exports").grid(row=0, column=0, columnspan=4, pady=5)

ctk.CTkLabel(export_frame, text="Images per A4 page:").grid(row=1, column=0, sticky="w", padx=5)
images_per_page_var = tk.StringVar(value="4")
images_per_page_entry = ctk.CTkEntry(export_frame, textvariable=images_per_page_var, width=60)
images_per_page_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

export_img_jpg_btn = ctk.CTkButton(export_frame, text="Export images (JPG)", command=export_images_jpg_clicked)
export_img_jpg_btn.grid(row=2, column=0, pady=5, padx=5, sticky="w")

export_img_pdf_btn = ctk.CTkButton(export_frame, text="Export images (PDF)", command=export_images_pdf_clicked)
export_img_pdf_btn.grid(row=2, column=1, pady=5, padx=5, sticky="w")

export_csv_btn = ctk.CTkButton(export_frame, text="Export results (CSV)", command=export_csv_clicked)
export_csv_btn.grid(row=2, column=2, pady=5, padx=5, sticky="w")

export_excel_btn = ctk.CTkButton(export_frame, text="Export results (Excel)", command=export_excel_clicked)
export_excel_btn.grid(row=2, column=3, pady=5, padx=5, sticky="e")

# ---------------- INIT ----------------
settings = load_settings()
row_var.set(settings.get("rows", "4"))
col_var.set(settings.get("cols", "4"))
color_var.set(settings.get("color", ""))
calc_mode_var.set(settings.get("calc_mode", "Manual"))

refresh_main_preview()

root.mainloop()
