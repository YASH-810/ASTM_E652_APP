
# 🧪 ASTM E-562 Manual Point Counting Application  
### **Python + OpenCV + CustomTkinter Desktop App (with .EXE installer)**

This project is a complete desktop application for performing **ASTM E-562 point counting** on microstructure images.  
It includes:

- Automatic grid overlay  
- Non-border interior intersection points  
- Manual phase classification (Inside = 1.0, Boundary = 0.5)  
- Real-time percentage calculation  
- CSV / Excel export  
- A4 image export (JPG/PDF)  
- Windows EXE creation  
- Full Installer (Setup.exe)

---

## 📌 Features

### ✅ 1. Load multiple microstructure images  
Supports:  
`JPG, JPEG, PNG, TIFF, BMP`

---

### ✅ 2. Auto-crops images to perfect square  
Ensures grid stays uniform and equally sized.

---

### ✅ 3. Automatic grid generation  
User sets:

- **H cells (vertical divisions)**
- **V cells (horizontal divisions)**
- **Grid color**

---

### ✅ 4. Smart intersection point generation  
🎯 **Points are placed inside the grid, NOT on borders**  
Formula:

```
x = (col + 1) * (W / (cols + 1))
y = (row + 1) * (H / (rows + 1))
```

Produces perfect NxN interior points.

---

### ✅ 5. Manual Classification  
Click any point → choose:

| Type      | Value | Color   |
|-----------|--------|----------|
| Inside    | 1.0    | green    |
| Boundary  | 0.5    | orange   |
| Reset     | 0      | gray     |

---

### ✅ 6. Percentage Calculation  
Matches ASTM E-562:

```
Volume % = ( Σ(point values) / Total Points ) × 100
```

Displayed and saved in results table.

---

### ✅ 7. Export Options  
You can export:

- **A4 JPG pages** (multiple images per page)  
- **A4 PDF pages**  
- **CSV results**  
- **Excel results (XLSX)**  

---

### ✅ 8. Full Windows App (.EXE)  
Built using:

```
pyinstaller --onefile --windowed astm_app.py
```

Runs on any Windows PC — no Python needed.

---

## 🚀 Installation (For Users)

### 1. Download the installer  
`ASTM_E562_Setup.exe`

### 2. Run the setup  
Choose installation folder (default: Program Files)

### 3. Launch the Application  
Start Menu → **ASTM E562 App**

---
## 📁 Project Structure

```
ASTM-E562-App/
│
├── astm_e652_app.py
├── astm_e652_app.exe            
├── README.md
├── sample_image                              
└── grid_settings.json     
```

---

## 🧩 Technologies Used
- Python  
- OpenCV  
- CustomTkinter  
- PIL (Pillow)  
- ReportLab  
- OpenPyXL  
- PyInstaller  

---

## 👨‍💻 Author
Yash Londhe
