import com.pokeemerald.experimental.controls.*;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.List;

/**
 * A desktop mock of the theme gallery for one category, drawn with the same
 * ThemeCard code the phone uses, laid out like ThemeGallery (tabs over a grid
 * of cards).
 * usage: GalleryPreview <dir with BG*.png> <category> <out.png> [width height]
 */
public final class GalleryPreview {
    public static void main(String[] a) throws Exception {
        File dir = new File(a[0]);
        String cat = a[1];
        int w = a.length > 4 ? Integer.parseInt(a[3]) : 2404, h = a.length > 4 ? Integer.parseInt(a[4]) : 1080;
        float dp = h / 411f;              // a 1080p phone in landscape is ~411dp tall
        BufferedImage out = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = out.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setColor(new Color(0x121519)); g.fillRect(0, 0, w, h);
        int pad = Math.round(12 * dp);
        g.setColor(Color.WHITE); g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, Math.round(22 * dp)));
        g.drawString("Themes", pad, Math.round(30 * dp));
        g.setColor(new Color(0x2FB87E)); g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, Math.round(16 * dp)));
        g.drawString("Done", w - pad - Math.round(50 * dp), Math.round(30 * dp));
        // tabs
        int x = pad, ty = Math.round(44 * dp), th = Math.round(34 * dp);
        g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, Math.round(15 * dp)));
        for (String c : Themes.CATEGORIES) {
            int n = Themes.in(c).size() + (c.equals(Themes.MINIMAL) ? 1 : 0);
            String label = c + "  " + n;
            int tw = g.getFontMetrics().stringWidth(label) + Math.round(28 * dp);
            g.setColor(new Color(c.equals(cat) ? 0x2FB87E : 0x2A3038));
            g.fillRoundRect(x, ty, tw, th, th, th);
            g.setColor(Color.WHITE);
            g.drawString(label, x + Math.round(14 * dp), ty + th / 2 + g.getFontMetrics().getAscent() / 2 - 2);
            x += tw + Math.round(8 * dp);
        }
        // grid
        List<Themes> list = Themes.in(cat);
        int width = w - 2 * pad, cols = Math.max(2, Math.min(5, (int) (width / (200 * dp))));
        int gap = Math.round(10 * dp), cw = (width - gap * (cols - 1)) / cols;
        int ih = (cw - 8) * ThemeCard.H / ThemeCard.W, y = ty + th + Math.round(12 * dp);
        int count = list.size() + (cat.equals(Themes.MINIMAL) ? 1 : 0);
        g.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, Math.round(13 * dp)));
        for (int k = 0; k < count && y < h; k++) {
            Themes t = k < list.size() ? list.get(k) : null;
            int cx = pad + (k % cols) * (cw + gap);
            if (k > 0 && k % cols == 0) y += ih + Math.round(34 * dp);
            g.setColor(new Color(0x1E232B)); g.fillRoundRect(cx, y, cw, ih + Math.round(28 * dp), 16, 16);
            if (k == 0) {        // as if the first were selected
                g.setColor(new Color(0x2FB87E)); g.setStroke(new BasicStroke(3 * dp));
                g.drawRoundRect(cx, y, cw, ih + Math.round(28 * dp), 16, 16);
            }
            g.drawImage(card(dir, t), cx + 4, y + 4, cw - 8, ih, null);
            g.setColor(new Color(0xE6EAF0));
            g.drawString(t == null ? "None (black)" : t.name, cx + 6, y + ih + Math.round(22 * dp));
        }
        g.dispose();
        ImageIO.write(out, "png", new File(a[2]));
    }

    static BufferedImage card(File dir, Themes t) throws Exception {
        BufferedImage img = new BufferedImage(ThemeCard.W, ThemeCard.H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        g.setColor(Color.BLACK); g.fillRect(0, 0, ThemeCard.W, ThemeCard.H);
        if (t != null && !t.isShell()) {
            BufferedImage bg = ImageIO.read(new File(dir, t.background == 0 ? "BG.png" : "BG" + t.background + ".png"));
            float s = Math.max(ThemeCard.W / (float) bg.getWidth(), ThemeCard.H / (float) bg.getHeight());
            int bw = Math.round(bg.getWidth() * s), bh = Math.round(bg.getHeight() * s);
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g.drawImage(bg, (ThemeCard.W - bw) / 2, (ThemeCard.H - bh) / 2, bw, bh, null);
        }
        ThemeCard.drawOver(new AwtPainter(g), t);
        g.dispose();
        return img;
    }
}
