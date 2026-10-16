import com.pokeemerald.experimental.controls.*;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;

/**
 * Checks every theme the way the phone shows it: the background cover-scaled
 * to the screen, the app's real control layout on top, at several phone
 * shapes. For each control it measures, over the background under it:
 *   - busyness: luminance standard deviation (a sprite edge or a sun disc
 *     behind a button reads as clutter and hides the button's outline), and
 *   - label contrast: the WCAG contrast ratio between the label colour and the
 *     button face composited over that background (min over light/dark areas).
 * Exit 1 if a gated theme fails (usage on main).
 */
public final class ThemeCheck {
    static final int[][] SCREENS = {{2400, 1080}, {2340, 1080}, {1920, 1080}, {2404, 1080}};
    static final double MAX_BUSY = 22.0, MIN_CONTRAST = 3.0;

    static double lum(int rgb) {
        double[] c = new double[3];
        for (int i = 0; i < 3; i++) {
            double v = ((rgb >> (16 - 8 * i)) & 0xFF) / 255.0;
            c[i] = v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    }
    static double contrast(int a, int b) {
        double x = lum(a), y = lum(b);
        return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
    }
    static int over(int argb, int rgb) {        // composite argb over opaque rgb
        double al = ((argb >>> 24) & 0xFF) / 255.0;
        int r = 0;
        for (int sh = 0; sh <= 16; sh += 8) {
            double f = (argb >> sh) & 0xFF, bk = (rgb >> sh) & 0xFF;
            r |= ((int) Math.round(f * al + bk * (1 - al)) & 0xFF) << sh;
        }
        return r;
    }

    /** Worst busyness and label contrast of one background with one style,
     *  over all SCREENS, and where the worst busyness was. */
    static Object[] measure(BufferedImage bg, ButtonStyle st) {
        double worstBusy = 0, worstContrast = 99; String where = "";
        for (int[] s : SCREENS) {
            int w = s[0], h = s[1];
            BufferedImage scr = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = scr.createGraphics();
            float sc = Math.max(w / (float) bg.getWidth(), h / (float) bg.getHeight());
            int bw = Math.round(bg.getWidth() * sc), bh = Math.round(bg.getHeight() * sc);
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g.drawImage(bg, (w - bw) / 2, (h - bh) / 2, bw, bh, null);
            g.dispose();
            ControlsLayout lay = new ControlsLayout(w, h, new Settings(), false);
            for (ControlsLayout.Item it : lay.items) {
                int x0 = Math.max(0, Math.round(it.cx - it.w / 2)), x1 = Math.min(w - 1, Math.round(it.cx + it.w / 2));
                int y0 = Math.max(0, Math.round(it.cy - it.h / 2)), y1 = Math.min(h - 1, Math.round(it.cy + it.h / 2));
                double sum = 0, sum2 = 0; int n = 0, light = 0, dark = 0xFFFFFF; double lmax = -1, lmin = 2;
                for (int y = y0; y <= y1; y += 2) for (int x = x0; x <= x1; x += 2) {
                    int p = scr.getRGB(x, y) & 0xFFFFFF;
                    double l = 0.299 * ((p >> 16) & 255) + 0.587 * ((p >> 8) & 255) + 0.114 * (p & 255);
                    sum += l; sum2 += l * l; n++;
                    double ll = lum(p);
                    if (ll > lmax) { lmax = ll; light = p; }
                    if (ll < lmin) { lmin = ll; dark = p; }
                }
                double sd = Math.sqrt(Math.max(0, sum2 / n - (sum / n) * (sum / n)));
                int face = it.shape == ControlsLayout.Shape.DPAD ? st.dpad
                        : "a".equals(it.id) && st.accentA != 0 ? st.accentA
                        : "b".equals(it.id) && st.accentB != 0 ? st.accentB : st.face;
                // The gear is backed dark by design.
                if (it.id.equals("gear")) continue;
                // What the eye sees behind the label: face over the dark
                // backing (ControlsRenderer.BACKING) over the art.
                int back = st.outlineOnly ? ControlsRenderer.BACKING_MINIMAL : ControlsRenderer.BACKING;
                int ink = ControlsRenderer.inkOn(st, face) & 0xFFFFFF;   // what the renderer draws
                double c = Math.min(contrast(ink, over(face, over(back, light))),
                                    contrast(ink, over(face, over(back, dark))));
                if (sd > worstBusy) { worstBusy = sd; where = it.id + "@" + w + "x" + h; }
                worstContrast = Math.min(worstContrast, c);
            }
        }
        return new Object[] {worstBusy, worstContrast, where};
    }

    static boolean report(String name, Object[] m, boolean gated) {
        double busy = (Double) m[0], contrast = (Double) m[1];
        boolean ok = busy <= MAX_BUSY && contrast >= MIN_CONTRAST;
        System.out.printf("%-4s %-18s busy %5.1f (worst %-14s)  label contrast %4.1f%s%n",
                ok ? "ok" : gated ? "FAIL" : "info", name, busy, m[2], contrast, gated ? "" : "  [not gated]");
        return ok || !gated;
    }

    /**
     * usage: ThemeCheck <dir with BG*.png> [--report-only i,j,...]
     *    or: ThemeCheck --file <png> <style index> ...   (measure candidates)
     */
    public static void main(String[] a) throws Exception {
        if (a.length > 0 && a[0].equals("--file")) {
            for (int i = 1; i + 1 < a.length; i += 2)
                report(new File(a[i]).getName(), measure(ImageIO.read(new File(a[i])),
                        ButtonStyle.ALL[Integer.parseInt(a[i + 1])]), true);
            return;
        }
        java.util.Set<Integer> reportOnly = new java.util.HashSet<>();
        if (a.length > 2 && a[1].equals("--report-only"))
            for (String x : a[2].split(",")) reportOnly.add(Integer.parseInt(x));
        int failures = 0;
        // make_themes.py's record of which picture each number is. A theme
        // whose number points at another theme's picture would pass every
        // other check here and still show the wrong art.
        File indexFile = new File(a[0], "themes-index.txt");
        if (!indexFile.isFile()) {
            System.out.println("MISSING " + indexFile + " (run make_themes.py)");
            failures++;
        } else {
            java.util.Map<Integer, String> index = new java.util.HashMap<>();
            for (String line : java.nio.file.Files.readAllLines(indexFile.toPath())) {
                String[] p = line.trim().split(" ");
                if (p.length == 2) index.put(Integer.parseInt(p[0]), p[1]);
            }
            for (Themes th : Themes.ALL) {
                if (th.isShell()) continue;
                if (!th.id.equals(index.get(th.background))) {
                    System.out.println("MISMATCH " + th.id + " is BG" + th.background + ", but make_themes.py made "
                            + index.get(th.background) + " there");
                    failures++;
                }
                index.remove(th.background);
            }
            for (java.util.Map.Entry<Integer, String> e : index.entrySet()) {
                System.out.println("UNLISTED BG" + e.getKey() + " " + e.getValue() + " is generated but not in Themes.java");
                failures++;
            }
        }
        for (Themes th : Themes.ALL) {
            if (th.isShell()) continue;
            File f = new File(a[0], th.background == 0 ? "BG.png" : "BG" + th.background + ".png");
            if (!f.isFile()) { System.out.println("MISSING " + f); failures++; continue; }
            if (!report(th.name, measure(ImageIO.read(f), ButtonStyle.ALL[th.style]),
                    !reportOnly.contains(th.background))) failures++;
        }
        System.out.println(failures == 0 ? "ALL THEMES PASS" : failures + " THEMES FAIL");
        System.exit(failures == 0 ? 0 : 1);
    }
}
