import com.pokeemerald.experimental.controls.Painter;
import java.awt.*;
import java.awt.geom.*;

/** Java2D implementation of the controls' Painter, for previews and tests. */
final class AwtPainter implements Painter {
    private final Graphics2D g;
    AwtPainter(Graphics2D g) {
        this.g = g;
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
    }
    private void c(int argb) { g.setColor(new Color(argb, true)); }
    public void fillCircle(float cx, float cy, float r, int argb) { c(argb); g.fill(new Ellipse2D.Float(cx - r, cy - r, 2 * r, 2 * r)); }
    public void strokeCircle(float cx, float cy, float r, float w, int argb) {
        c(argb); g.setStroke(new BasicStroke(w)); g.draw(new Ellipse2D.Float(cx - r, cy - r, 2 * r, 2 * r)); }
    public void fillRoundRect(float l, float t, float r, float b, float rad, int argb) {
        c(argb); g.fill(new RoundRectangle2D.Float(l, t, r - l, b - t, 2 * rad, 2 * rad)); }
    public void strokeRoundRect(float l, float t, float r, float b, float rad, float w, int argb) {
        c(argb); g.setStroke(new BasicStroke(w)); g.draw(new RoundRectangle2D.Float(l, t, r - l, b - t, 2 * rad, 2 * rad)); }
    public void fillTriangle(float x1, float y1, float x2, float y2, float x3, float y3, int argb) {
        c(argb); Path2D.Float p = new Path2D.Float(); p.moveTo(x1, y1); p.lineTo(x2, y2); p.lineTo(x3, y3); p.closePath(); g.fill(p); }
    public void fillPolygon(float[] xy, int argb) {
        c(argb); Path2D.Float p = new Path2D.Float(); p.moveTo(xy[0], xy[1]);
        for (int i = 2; i < xy.length; i += 2) p.lineTo(xy[i], xy[i + 1]);
        p.closePath(); g.fill(p); }
    public void fillRectGradient(float l, float t, float r, float b, int top, int bottom, float g0, float g1) {
        g.setPaint(new GradientPaint(0, g0, new Color(top, true), 0, g1, new Color(bottom, true)));
        g.fill(new Rectangle2D.Float(l, t, r - l, b - t)); }
    public void fillCircleRadial(float cx, float cy, float r, float fx, float fy, int inner, int outer) {
        g.setPaint(new RadialGradientPaint(new Point2D.Float(fx, fy), Math.max(1, r), new float[] {0f, 1f},
                new Color[] {new Color(inner, true), new Color(outer, true)}));
        g.fill(new Ellipse2D.Float(cx - r, cy - r, 2 * r, 2 * r)); }
    public void text(String s, float cx, float cy, float size, int argb) {
        c(argb); g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, Math.max(1, Math.round(size))));
        FontMetrics m = g.getFontMetrics();
        g.drawString(s, cx - m.stringWidth(s) / 2f, cy + (m.getAscent() - m.getDescent()) / 2f);
    }
}
