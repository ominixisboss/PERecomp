import com.pokeemerald.experimental.controls.FrameSlices;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;

/** Draws a border frame (FRAMEn.png) the way GbaControlsView.drawFrame does, for previews. */
final class AwtFrames {
    static void draw(Graphics2D g, File dir, String name, int gl, int gt, int gr, int gb,
                     float scale, int w, int h) throws Exception {
        File f = new File(dir, name + ".png");
        if (!f.isFile()) return;
        BufferedImage img = ImageIO.read(f);
        Object hint = g.getRenderingHint(RenderingHints.KEY_INTERPOLATION);
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
        for (FrameSlices.Piece p : FrameSlices.place(img.getWidth(), gl, gt, gr, gb, scale, w, h))
            g.drawImage(img, Math.round(p.l), Math.round(p.t), Math.round(p.r), Math.round(p.b),
                    p.sx, p.sy, p.sx + p.sw, p.sy + p.sh, null);
        if (hint != null) g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, hint);
    }
}
