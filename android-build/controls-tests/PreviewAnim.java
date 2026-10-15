import com.pokeemerald.experimental.controls.*;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;

/**
 * Renders the press animation frame by frame at 60fps through the real
 * animator and renderer, for a scripted sequence of presses.
 * usage: PreviewAnim <style> <game-frame.png> <outdir> [w h] [crop: left|right|full]
 */
public final class PreviewAnim {
    // {start ms, end ms, keys}
    static final int[][] SCRIPT = {
        {100, 420, Keys.RIGHT}, {560, 880, Keys.UP}, {1020, 1340, Keys.UP | Keys.LEFT},
        {1480, 1800, Keys.DOWN}, {1940, 2120, Keys.A}, {2260, 2440, Keys.B}, {2580, 2760, Keys.START},
        {2900, 3080, Keys.L}, {3200, 3400, 0}};

    public static void main(String[] a) throws Exception {
        ButtonStyle st = ButtonStyle.ALL[Integer.parseInt(a[0])];
        BufferedImage game = ImageIO.read(new File(a[1]));
        File out = new File(a[2]); out.mkdirs();
        int w = a.length > 3 ? Integer.parseInt(a[3]) : 2400, h = a.length > 4 ? Integer.parseInt(a[4]) : 1080;
        String crop = a.length > 5 ? a[5] : "full";
        Settings s = new Settings();
        ControlsLayout lay = new ControlsLayout(w, h, s, false);
        ControlsAnimator anim = new ControlsAnimator();
        int frames = 3400 * 60 / 1000;
        for (int f = 0; f < frames; f++) {
            int ms = f * 1000 / 60, pressed = 0;
            for (int[] e : SCRIPT) if (ms >= e[0] && ms < e[1]) pressed |= e[2];
            anim.step(lay, pressed, f * 1_000_000_000L / 60);
            BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
            Graphics2D g = img.createGraphics();
            g.setColor(Color.BLACK); g.fillRect(0, 0, w, h);
            int gs = Math.max(1, Math.min(w / 240, h / 160));
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
            g.drawImage(game, lay.gameL, lay.gameT, 240 * gs, 160 * gs, null);
            ControlsRenderer.draw(new AwtPainter(g), lay, st, s.opacity, pressed, anim, st.gba);
            BufferedImage o = img;
            if (crop.equals("left")) o = img.getSubimage(0, 0, lay.gameL + 60, h);
            if (crop.equals("right")) o = img.getSubimage(lay.gameR - 60, 0, w - lay.gameR + 60, h);
            ImageIO.write(o, "png", new File(out, String.format("f%03d.png", f)));
        }
    }
}
