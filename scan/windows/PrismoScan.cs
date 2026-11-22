// PRISMO scan for Windows: tray icon, one quiet connection to oracle, opens whatever PRISMO scans.
// links and text go to Chrome, pictures to the photo viewer. built by install.cmd with the csc.exe
// every Windows already has, so no Visual Studio needed.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

class Scan
{
    public string Text, Type, To;
    public double At;
}

static class Program
{
    public const string Server = "https://132-226-199-122.sslip.io";
    public static readonly string Dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "prismo-scan");

    [STAThread]
    static void Main()
    {
        bool fresh;
        var one = new Mutex(true, "PrismoScanOnlyOnce", out fresh);
        if (!fresh) return;
        ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; // tls 1.2
        ServicePointManager.DefaultConnectionLimit = 4;
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Tray());
        GC.KeepAlive(one);
    }
}

class Tray : ApplicationContext
{
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO i);
    [DllImport("kernel32.dll")] static extern bool SetProcessWorkingSetSize(IntPtr p, IntPtr min, IntPtr max);
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr h);

    NotifyIcon icon;
    Icon normal, done, off;
    ScanWindow panel;
    SynchronizationContext ui;
    string key, dev;
    volatile bool running = true;
    int okState = -1;

    public Tray()
    {
        ui = new WindowsFormsSynchronizationContext();
        SynchronizationContext.SetSynchronizationContext(ui);
        Directory.CreateDirectory(Program.Dir);
        dev = ReadFile("dev");
        if (dev == "") { dev = Guid.NewGuid().ToString(); File.WriteAllText(Path.Combine(Program.Dir, "dev"), dev); }
        key = ReadFile("key");

        normal = MakeIcon(Color.White);
        done = MakeIcon(Color.FromArgb(80, 220, 120));
        off = MakeIcon(Color.FromArgb(120, 120, 120));
        icon = new NotifyIcon { Icon = off, Text = "PRISMO", Visible = true };
        var menu = new ContextMenuStrip();
        menu.Items.Add("Key", null, delegate { AskKey(); });
        menu.Items.Add("Quit", null, delegate { Quit(); });
        icon.ContextMenuStrip = menu;
        icon.MouseClick += delegate(object s, MouseEventArgs e) { if (e.Button == MouseButtons.Left) Toggle(); };
        panel = new ScanWindow(this);

        StartAtLogin();
        SystemEvents.PowerModeChanged += delegate(object s, PowerModeChangedEventArgs e) { if (e.Mode == PowerModes.Resume) wake.Set(); };
        if (key == "") AskKey();
        new Thread(PollLoop) { IsBackground = true }.Start();
        Trim();
    }

    public string Key { get { return key; } }

    static string ReadFile(string name)
    {
        try { return File.ReadAllText(Path.Combine(Program.Dir, name)).Trim(); } catch { return ""; }
    }

    static void StartAtLogin()
    {
        try
        {
            using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true))
                k.SetValue("PrismoScan", "\"" + Application.ExecutablePath + "\"");
        }
        catch { }
    }

    // the tray icon: the corners of a QR code, drawn so there's no .ico file to carry around
    Icon MakeIcon(Color c)
    {
        using (var b = new Bitmap(32, 32))
        using (var g = Graphics.FromImage(b))
        using (var p = new Pen(c, 3))
        using (var br = new SolidBrush(c))
        {
            g.SmoothingMode = SmoothingMode.None;
            foreach (var pt in new[] { new Point(2, 2), new Point(18, 2), new Point(2, 18) })
            {
                g.DrawRectangle(p, pt.X + 1, pt.Y + 1, 10, 10);
                g.FillRectangle(br, pt.X + 5, pt.Y + 5, 4, 4);
            }
            g.FillRectangle(br, 19, 19, 4, 4);
            g.FillRectangle(br, 25, 25, 5, 5);
            g.FillRectangle(br, 25, 19, 3, 3);
            g.FillRectangle(br, 19, 26, 3, 4);
            IntPtr h = b.GetHicon();
            var ic = (Icon)Icon.FromHandle(h).Clone();
            DestroyIcon(h);
            return ic;
        }
    }

    void SetState(bool ok)
    {
        int s = ok ? 1 : 0;
        if (s == okState) return;
        okState = s;
        icon.Icon = ok ? normal : off;
    }

    // give memory back while nothing is happening
    public static void Trim()
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        SetProcessWorkingSetSize(Process.GetCurrentProcess().Handle, (IntPtr)(-1), (IntPtr)(-1));
    }

    // --- the long-poll: one request open, oracle answers when there's a scan or after 25 s ---

    AutoResetEvent wake = new AutoResetEvent(false);

    static uint IdleSeconds()
    {
        var i = new LASTINPUTINFO();
        i.cbSize = (uint)Marshal.SizeOf(i);
        if (!GetLastInputInfo(ref i)) return 0;
        return ((uint)Environment.TickCount - i.dwTime) / 1000;
    }

    public static HttpWebRequest Request(string path, string key, int timeout)
    {
        var r = (HttpWebRequest)WebRequest.Create(Program.Server + path);
        r.Headers["X-Scan-Key"] = key;
        r.Timeout = timeout;
        r.ReadWriteTimeout = timeout;
        r.UserAgent = "PrismoScan/1.0 windows";
        return r;
    }

    void PollLoop()
    {
        int backoff = 2;
        var js = new JavaScriptSerializer();
        while (running)
        {
            if (key == "") { wake.WaitOne(5000); continue; }
            string path = "/scan/wait?kind=win&dev=" + Uri.EscapeDataString(dev) + "&name=" +
                          Uri.EscapeDataString(Environment.MachineName) + "&idle=" + IdleSeconds();
            try
            {
                string body;
                using (var resp = (HttpWebResponse)Request(path, key, 45000).GetResponse())
                using (var rd = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                    body = rd.ReadToEnd();
                backoff = 2;
                var list = ParseScans(js, body);
                ui.Post(delegate
                {
                    SetState(true);
                    foreach (var s in list) { Open(s); Flash(); }
                }, null);
            }
            catch (WebException e)
            {
                var hr = e.Response as HttpWebResponse;
                bool badKey = hr != null && (int)hr.StatusCode == 403;
                ui.Post(delegate { SetState(false); if (badKey) AskKey(); }, null);
                if (badKey) { key = ""; continue; }
                wake.WaitOne(backoff * 1000);
                backoff = Math.Min(backoff * 2, 60);
            }
            catch (Exception)
            {
                wake.WaitOne(backoff * 1000);
                backoff = Math.Min(backoff * 2, 60);
            }
        }
    }

    public static List<Scan> ParseScans(JavaScriptSerializer js, string body)
    {
        var outp = new List<Scan>();
        var d = js.Deserialize<Dictionary<string, object>>(body);
        object arr;
        if (d == null || !d.TryGetValue("scans", out arr) || !(arr is ArrayList)) return outp;
        foreach (object o in (ArrayList)arr)
        {
            var m = o as Dictionary<string, object>;
            if (m == null) continue;
            var s = new Scan();
            s.Text = m.ContainsKey("text") ? Convert.ToString(m["text"]) : "";
            s.Type = m.ContainsKey("type") ? Convert.ToString(m["type"]) : "";
            s.To = m.ContainsKey("to") && m["to"] != null ? Convert.ToString(m["to"]) : null;
            s.At = m.ContainsKey("at") ? Convert.ToDouble(m["at"]) : 0;
            outp.Add(s);
        }
        return outp;
    }

    void Flash()
    {
        icon.Icon = done;
        var t = new System.Windows.Forms.Timer { Interval = 1500 };
        t.Tick += delegate { t.Stop(); t.Dispose(); icon.Icon = okState == 1 ? normal : off; };
        t.Start();
    }

    // --- opening things ---

    public static bool IsImage(string t)
    {
        if (t.StartsWith("data:image/")) return true;
        Uri u;
        if (!Uri.TryCreate(t, UriKind.Absolute, out u) || !u.Scheme.StartsWith("http")) return false;
        string ext = Path.GetExtension(u.AbsolutePath).ToLowerInvariant();
        return Array.IndexOf(new[] { ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp" }, ext) >= 0;
    }

    public static bool IsLink(string t)
    {
        string l = t.ToLowerInvariant();
        return l.StartsWith("http://") || l.StartsWith("https://") || l.StartsWith("www.");
    }

    public void Open(Scan s)
    {
        string t = s.Text.Trim();
        if (t == "") return;
        if (IsImage(t)) { ShowImage(t); return; }
        string url = IsLink(t)
            ? (t.ToLowerInvariant().StartsWith("www.") ? "https://" + t : t)
            : "https://www.google.com/search?q=" + Uri.EscapeDataString(t);
        try { Process.Start("chrome.exe", "\"" + url.Replace("\"", "%22") + "\""); }
        catch { try { Process.Start(url); } catch { } }
    }

    void ShowImage(string t)
    {
        string dir = Path.Combine(Path.GetTempPath(), "prismo-scan");
        Directory.CreateDirectory(dir);
        string stamp = DateTime.Now.ToString("yyyyMMdd-HHmmss");
        if (t.StartsWith("data:image/"))
        {
            int comma = t.IndexOf(',');
            if (comma < 0) return;
            string head = t.Substring(11, comma - 11);
            string ext = head.Split(';')[0];
            if (ext == "" || ext.Length > 5) ext = "png";
            string file = Path.Combine(dir, "scan-" + stamp + "." + ext);
            try { File.WriteAllBytes(file, Convert.FromBase64String(t.Substring(comma + 1))); Process.Start(file); } catch { }
            return;
        }
        ThreadPool.QueueUserWorkItem(delegate
        {
            try
            {
                string file = Path.Combine(dir, "scan-" + stamp + Path.GetExtension(new Uri(t).AbsolutePath));
                using (var wc = new WebClient()) wc.DownloadFile(t, file);
                Process.Start(file);
            }
            catch { }
        });
    }

    // --- the key, asked once ---

    void AskKey()
    {
        using (var f = new Form())
        {
            f.Text = "PRISMO scan key";
            f.FormBorderStyle = FormBorderStyle.FixedDialog;
            f.StartPosition = FormStartPosition.CenterScreen;
            f.MaximizeBox = f.MinimizeBox = false;
            f.ClientSize = new Size(340, 80);
            f.TopMost = true;
            var tb = new TextBox { Left = 12, Top = 14, Width = 316, Text = key };
            var ok = new Button { Text = "OK", Left = 248, Top = 46, Width = 80, DialogResult = DialogResult.OK };
            f.Controls.Add(tb);
            f.Controls.Add(ok);
            f.AcceptButton = ok;
            if (f.ShowDialog() != DialogResult.OK) return;
            key = tb.Text.Trim();
            File.WriteAllText(Path.Combine(Program.Dir, "key"), key);
            wake.Set();
        }
    }

    void Toggle()
    {
        if (panel.Visible) panel.Hide(); else panel.ShowNearTray();
    }

    void Quit()
    {
        running = false;
        icon.Visible = false;
        icon.Dispose();
        ExitThread();
    }
}

// the window: live camera + recent scans. nothing runs while it's closed
class ScanWindow : Form
{
    Tray tray;
    PictureBox cam;
    FlowLayoutPanel rows;
    System.Windows.Forms.Timer camTimer;
    volatile bool camBusy;
    List<Scan> recent = new List<Scan>();
    static readonly Color Bg = Color.FromArgb(28, 28, 32), Fg = Color.FromArgb(235, 235, 240), Dim = Color.FromArgb(120, 120, 130);

    public ScanWindow(Tray t)
    {
        tray = t;
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        TopMost = true;
        BackColor = Bg;
        ClientSize = new Size(344, 480);
        Padding = new Padding(12);
        StartPosition = FormStartPosition.Manual;

        cam = new PictureBox { Left = 12, Top = 12, Width = 320, Height = 240, BackColor = Color.Black, SizeMode = PictureBoxSizeMode.Zoom };
        rows = new FlowLayoutPanel
        {
            Left = 12, Top = 262, Width = 320, Height = 206, AutoScroll = true,
            FlowDirection = FlowDirection.TopDown, WrapContents = false, BackColor = Bg
        };
        Controls.Add(cam);
        Controls.Add(rows);

        camTimer = new System.Windows.Forms.Timer { Interval = 350 };
        camTimer.Tick += delegate { Frame(); };
        Deactivate += delegate { Hide(); };
        VisibleChanged += delegate
        {
            if (Visible) { cam.Image = Glyph("", 40, Dim, 320, 240); LoadRecent(); Frame(); camTimer.Start(); }
            else { camTimer.Stop(); SetCam(null); Tray.Trim(); }
        };
    }

    protected override CreateParams CreateParams
    {
        get { var p = base.CreateParams; p.ClassStyle |= 0x20000; return p; } // drop shadow
    }

    public void ShowNearTray()
    {
        var wa = Screen.FromPoint(Cursor.Position).WorkingArea;
        Location = new Point(wa.Right - Width - 12, wa.Bottom - Height - 12);
        Show();
        Activate();
    }

    void SetCam(Image img)
    {
        var old = cam.Image;
        cam.Image = img;
        if (old != null) old.Dispose();
    }

    void Frame()
    {
        if (camBusy) return;
        camBusy = true;
        string key = tray.Key;
        ThreadPool.QueueUserWorkItem(delegate
        {
            Image img = null;
            try
            {
                using (var resp = Tray.Request("/scan/cam.jpg", key, 6000).GetResponse())
                using (var ms = new MemoryStream())
                {
                    resp.GetResponseStream().CopyTo(ms);
                    ms.Position = 0;
                    img = Image.FromStream(new MemoryStream(ms.ToArray()));
                }
            }
            catch { }
            try
            {
                BeginInvoke((MethodInvoker)delegate
                {
                    camBusy = false;
                    if (!Visible) { if (img != null) img.Dispose(); return; }
                    SetCam(img ?? Glyph("", 40, Dim, 320, 240));
                });
            }
            catch { camBusy = false; }
        });
    }

    void LoadRecent()
    {
        string key = tray.Key;
        ThreadPool.QueueUserWorkItem(delegate
        {
            List<Scan> list;
            try
            {
                string body;
                using (var resp = Tray.Request("/scan/recent", key, 6000).GetResponse())
                using (var rd = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                    body = rd.ReadToEnd();
                list = Tray.ParseScans(new JavaScriptSerializer(), body);
            }
            catch { return; }
            try { BeginInvoke((MethodInvoker)delegate { Fill(list); }); } catch { }
        });
    }

    void Fill(List<Scan> list)
    {
        recent = list;
        rows.SuspendLayout();
        foreach (Control c in rows.Controls) c.Dispose();
        rows.Controls.Clear();
        if (list.Count == 0)
            rows.Controls.Add(new PictureBox { Width = 300, Height = 60, Image = Glyph("", 22, Dim, 300, 60) });
        for (int i = 0; i < list.Count; i++)
        {
            var s = list[i];
            var row = new Label
            {
                Width = 296, Height = 26, ForeColor = Fg, BackColor = Bg, Cursor = Cursors.Hand,
                Font = new Font("Segoe UI", 9.5f), AutoEllipsis = true, Tag = i,
                Text = s.Text.Replace("\r", " ").Replace("\n", " "),
                Image = Glyph(IconFor(s), 11, Dim, 22, 22), ImageAlign = ContentAlignment.MiddleLeft,
                TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(24, 0, 54, 0)
            };
            var when = new Label
            {
                Text = Ago(s.At), ForeColor = s.To == null ? Color.FromArgb(75, 75, 82) : Dim, BackColor = Bg, Width = 50, Height = 26,
                Font = new Font("Segoe UI", 8.5f), TextAlign = ContentAlignment.MiddleRight, Left = 246, Top = 0
            };
            row.Controls.Add(when);
            row.Click += delegate(object o, EventArgs e) { int n = (int)((Label)o).Tag; Hide(); tray.Open(recent[n]); };
            row.MouseEnter += delegate(object o, EventArgs e) { ((Label)o).BackColor = Color.FromArgb(44, 44, 50); };
            row.MouseLeave += delegate(object o, EventArgs e) { ((Label)o).BackColor = Bg; };
            rows.Controls.Add(row);
        }
        rows.ResumeLayout();
    }

    static string IconFor(Scan s)
    {
        if (Tray.IsImage(s.Text)) return "";   // photo
        if (Tray.IsLink(s.Text)) return "";    // link
        if (s.Type != "QR-Code" && s.Type != "TEST") return ""; // barcode-ish
        return "";                              // text
    }

    static string Ago(double at)
    {
        double sec = (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds - at;
        if (sec < 60) return "now";
        if (sec < 3600) return (int)(sec / 60) + "m";
        if (sec < 86400) return (int)(sec / 3600) + "h";
        return (int)(sec / 86400) + "d";
    }

    // windows' own icon font, so no image files
    static Image Glyph(string ch, float size, Color c, int w, int h)
    {
        var b = new Bitmap(w, h);
        using (var g = Graphics.FromImage(b))
        using (var f = new Font("Segoe MDL2 Assets", size))
        using (var br = new SolidBrush(c))
        {
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
            var sz = g.MeasureString(ch, f);
            g.DrawString(ch, f, br, (w - sz.Width) / 2, (h - sz.Height) / 2);
        }
        return b;
    }
}
