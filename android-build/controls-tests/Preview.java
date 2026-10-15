import com.pokeemerald.experimental.controls.*;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;

/**
 * Renders the overlay exactly as the phone draws it -- same layout, same
 * renderer -- over a theme background and a game frame, to a PNG.
 * usage: Preview <bg.png|none> <game-frame.png> <style|-1> <out.png> [w h] [edit] [pressedMask] [scale] [opacity]
 */
public final class Preview {
    public static void main(String[] a) throws Exception {
        int w = a.length > 4 ? Integer.parseInt(a[4]) : 2400, h = a.length > 5 ? Integer.parseInt(a[5]) : 1080;
        boolean edit = a.length > 6 && a[6].equals("edit");
        int pressed = a.length > 7 ? Integer.decode(a[7]) : 0;
        Settings s = new Settings();
        if (a.length > 8) s.scale = Float.parseFloat(a[8]);
        if (a.length > 9) s.opacity = Float.parseFloat(a[9]);
        BufferedImage out = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = out.createGraphics();
        g.setColor(Color.BLACK); g.fillRect(0, 0, w, h);
        if (!a[0].equals("none")) {          // cover-scale, as GbaControlsView does
            BufferedImage bg = ImageIO.read(new File(a[0]));
            float sc = Math.max(w / (float) bg.getWidth(), h / (float) bg.getHeight());
            int bw = Math.round(bg.getWidth() * sc), bh = Math.round(bg.getHeight() * sc);
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g.drawImage(bg, (w - bw) / 2, (h - bh) / 2, bw, bh, null);
        }
        BufferedImage game = ImageIO.read(new File(a[1]));
        int gs = Math.max(1, Math.min(w / 240, h / 160));
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
        g.drawImage(game, (w - 240 * gs) / 2, (h - 160 * gs) / 2, 240 * gs, 160 * gs, null);
        // The fork's Border.png frame, exactly where and when the phone draws
        // it (GbaControlsView.drawBorder), so previews match the device.
        String bgName = new File(a[0]).getName();
        int bgIndex = bgName.equals("BG.png") ? 0 : bgName.matches("BG\\d+\\.png") ? Integer.parseInt(bgName.replaceAll("\\D", "")) : -1;
        File borderPng = new File(new File(a[0]).getParentFile() == null ? new File(".") : new File(a[0]).getParentFile(), "Border.png");
        if (bgIndex >= 0 && Themes.wantsBorderFrame(bgIndex) && borderPng.isFile()) {
            BufferedImage border = ImageIO.read(borderPng);
            int iw = 240 * gs - 2, ih = 160 * gs - 2, gx = (w - 240 * gs) / 2, gy = (h - 160 * gs) / 2;
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            int dx1 = gx + 1 - iw * 19 / 961, dy1 = gy + 1 - ih * 20 / 643;
            int dx2 = gx + 1 + iw + iw * 20 / 961, dy2 = gy + 1 + ih + ih * 20 / 643;
            g.drawImage(border, dx1, dy1, dx2, dy2, 141, 18, 1141, 701, null);
        }
        int style = Integer.parseInt(a[2]);
        ControlsLayout lay = new ControlsLayout(w, h, s, edit);
        ButtonStyle st = ButtonStyle.ALL[Math.max(0, style)];
        ControlsRenderer.draw(new AwtPainter(g), lay, st, s.opacity, pressed, null, st.gba && a[0].equals("none"));
        ImageIO.write(out, "png", new File(a[3]));
    }
}
