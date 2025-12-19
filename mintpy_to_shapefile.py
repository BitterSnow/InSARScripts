# mintpy_to_shapefile_direct.py
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import h5py
import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()

def xy2coor(x, y, gt):
    return gt[0] + x * gt[1] + y * gt[2], gt[3] + x * gt[4] + y * gt[5]

class MintPyToShapefileApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MintPy SBAS 转 Shapefile（直读 HDF5）")
        self.root.geometry("600x350")

        self.work_dir = tk.StringVar()
        self.h5_file = tk.StringVar()
        self.vel_tiff = tk.StringVar()
        self.pixel_span = tk.IntVar(value=1)

        self.create_widgets()

    def create_widgets(self):
        pad = {'padx': 10, 'pady': 5}
        tk.Label(self.root, text="工作目录（输出路径）:").grid(row=0, column=0, sticky='w', **pad)
        tk.Entry(self.root, textvariable=self.work_dir, width=50).grid(row=0, column=1, **pad)
        tk.Button(self.root, text="浏览", command=self.select_work_dir).grid(row=0, column=2, **pad)

        tk.Label(self.root, text="TimeSeries HDF5 文件:").grid(row=1, column=0, sticky='w', **pad)
        tk.Entry(self.root, textvariable=self.h5_file, width=50).grid(row=1, column=1, **pad)
        tk.Button(self.root, text="选择", command=self.select_h5).grid(row=1, column=2, **pad)

        tk.Label(self.root, text="Velocity GeoTIFF:").grid(row=2, column=0, sticky='w', **pad)
        tk.Entry(self.root, textvariable=self.vel_tiff, width=50).grid(row=2, column=1, **pad)
        tk.Button(self.root, text="选择", command=self.select_vel_tiff).grid(row=2, column=2, **pad)

        tk.Label(self.root, text="点采样间隔（像素）:").grid(row=3, column=0, sticky='w', **pad)
        tk.Spinbox(self.root, from_=1, to=100, textvariable=self.pixel_span, width=10).grid(row=3, column=1, sticky='w', **pad)

        tk.Button(self.root, text="开始转换", command=self.run_conversion, bg="lightgreen", height=2).grid(row=4, column=1, pady=20)

        self.log_text = tk.Text(self.root, height=6, state='disabled')
        self.log_text.grid(row=5, column=0, columnspan=3, **pad)

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.root.update()

    def select_work_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.work_dir.set(folder)

    def select_h5(self):
        file = filedialog.askopenfilename(filetypes=[("HDF5 files", "*.h5")])
        if file:
            self.h5_file.set(file)

    def select_vel_tiff(self):
        file = filedialog.askopenfilename(filetypes=[("GeoTIFF", "*.tif *.tiff")])
        if file:
            self.vel_tiff.set(file)

    def run_conversion(self):
        try:
            work_dir = self.work_dir.get().strip()
            h5_path = self.h5_file.get().strip()
            vel_path = self.vel_tiff.get().strip()
            span = self.pixel_span.get()

            if not all([work_dir, h5_path, vel_path]):
                messagebox.showerror("错误", "请填写所有路径！")
                return

            self.log("正在从 HDF5 生成 Shapefile...")
            count = self.generate_shapefile_direct(vel_path, h5_path, work_dir, span)
            self.log(f"✅ 成功生成 {count} 个点。输出文件：sbas_points.shp")
            messagebox.showinfo("完成", f"Shapefile 已生成！\n共 {count} 个有效点。")

        except Exception as e:
            self.log(f"❌ 错误: {str(e)}")
            messagebox.showerror("错误", str(e))

    def generate_shapefile_direct(self, vel_tiff_path, h5_file_path, out_dir, pixel_span=1):
        # --- 读 velocity ---
        vel_ds = gdal.Open(vel_tiff_path)
        gt = vel_ds.GetGeoTransform()
        x_size = vel_ds.RasterXSize
        y_size = vel_ds.RasterYSize
        vel_array = vel_ds.GetRasterBand(1).ReadAsArray()
        vel_ds = None

        # --- 读 HDF5 ---
        with h5py.File(h5_file_path, 'r') as f:
            dates = [d.decode('utf-8') for d in f['date'][:]]
            ts_data = f['timeseries'][:]

        if ts_data.shape[1:] != (y_size, x_size):
            raise ValueError("HDF5 与 velocity 尺寸不匹配！")

        # --- 创建 Shapefile ---
        shp_path = os.path.join(out_dir, "sbas_points.shp")
        prj_path = os.path.join(out_dir, "sbas_points.prj")

        driver = ogr.GetDriverByName("ESRI Shapefile")
        if os.path.exists(shp_path):
            driver.DeleteDataSource(shp_path)
        ds_shp = driver.CreateDataSource(shp_path)
        layer = ds_shp.CreateLayer("sbas_points", geom_type=ogr.wkbPoint)

        layer.CreateField(ogr.FieldDefn("vel", ogr.OFTReal))
        for date in dates:
            layer.CreateField(ogr.FieldDefn(f"D{date}", ogr.OFTReal))

        feature_defn = layer.GetLayerDefn()
        valid_count = 0

        for x in range(0, x_size, pixel_span):
            for y in range(0, y_size, pixel_span):
                v = vel_array[y, x]
                if np.isnan(v) or v == 0.0 or abs(v) > 100:
                    continue

                point = ogr.Geometry(ogr.wkbPoint)
                gx, gy = xy2coor(x, y, gt)
                point.AddPoint(gx, gy)

                feat = ogr.Feature(feature_defn)
                feat.SetGeometry(point)
                feat.SetField("vel", float(v * 1000))
                for i, date in enumerate(dates):
                    disp = ts_data[i, y, x]
                    feat.SetField(f"D{date}", float(disp * 1000))
                layer.CreateFeature(feat)
                feat = None
                valid_count += 1

        ds_shp = None

        # .prj
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        srs.MorphToESRI()
        with open(prj_path, 'w') as f:
            f.write(srs.ExportToWkt())

        return valid_count

if __name__ == "__main__":
    root = tk.Tk()
    app = MintPyToShapefileApp(root)
    root.mainloop()