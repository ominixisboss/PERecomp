import com.pokeemerald.experimental.controls.*;

/** Plain-JVM tests for the touch controls' logic. Exit status 1 on failure. */
public final class ControlsTest {
    static int failures;
    static void check(boolean ok, String what) {
        if (!ok) { failures++; System.out.println("FAIL: " + what); }
    }

    public static void main(String[] args) {
        Settings s = new Settings();
        for (int[] size : new int[][] {{2400, 1080}, {1920, 1080}, {2340, 1080}, {1280, 720}}) {
            ControlsLayout lay = new ControlsLayout(size[0], size[1], s, false);
            String at = size[0] + "x" + size[1] + ": ";
            ControlsLayout.Item d = lay.find(ControlsLayout.DPAD);
            float r = d.radius();
            // Cardinals, at several distances across the live area.
            for (float f : new float[] {0.4f, 0.8f, 1.15f}) {
                check(lay.dpadKeys(d, d.cx + r * f, d.cy) == Keys.RIGHT, at + "right @" + f);
                check(lay.dpadKeys(d, d.cx - r * f, d.cy) == Keys.LEFT, at + "left @" + f);
                check(lay.dpadKeys(d, d.cx, d.cy - r * f) == Keys.UP, at + "up @" + f);
                check(lay.dpadKeys(d, d.cx, d.cy + r * f) == Keys.DOWN, at + "down @" + f);
            }
            // 20 degrees off a cardinal is still that cardinal alone.
            double a = Math.toRadians(20);
            check(lay.dpadKeys(d, d.cx + (float) Math.cos(a) * r * .7f, d.cy - (float) Math.sin(a) * r * .7f) == Keys.RIGHT,
                    at + "near-right stays right");
            // Exact diagonals press both.
            float q = r * 0.6f;
            check(lay.dpadKeys(d, d.cx + q, d.cy - q) == (Keys.UP | Keys.RIGHT), at + "up-right");
            check(lay.dpadKeys(d, d.cx - q, d.cy + q) == (Keys.DOWN | Keys.LEFT), at + "down-left");
            check(lay.dpadKeys(d, d.cx - q, d.cy - q) == (Keys.UP | Keys.LEFT), at + "up-left");
            check(lay.dpadKeys(d, d.cx + q, d.cy + q) == (Keys.DOWN | Keys.RIGHT), at + "down-right");
            check(lay.dpadKeys(d, d.cx + 2, d.cy + 2) == 0, at + "dead centre");
            // Every control is on screen and hit-tests to itself.
            for (ControlsLayout.Item it : lay.items) {
                check(it.cx - it.w / 2 >= -1 && it.cx + it.w / 2 <= size[0] + 1
                        && it.cy - it.h / 2 >= -1 && it.cy + it.h / 2 <= size[1] + 1, at + it.id + " on screen");
                check(lay.itemAt(it.cx, it.cy) == it, at + it.id + " hit-tests to itself");
            }
            // No two controls overlap -- a press must never land on two.
            for (ControlsLayout.Item p : lay.items) for (ControlsLayout.Item o : lay.items) {
                if (p == o) continue;
                boolean overlapX = Math.abs(p.cx - o.cx) < (p.w + o.w) / 2;
                boolean overlapY = Math.abs(p.cy - o.cy) < (p.h + o.h) / 2;
                check(!(overlapX && overlapY), at + p.id + " overlaps " + o.id);
            }
            // The ball button is L+R together; game screen area is not a control.
            check(lay.find("ball").keys == (Keys.L | Keys.R), at + "ball = L+R");
            check(lay.itemAt(size[0] / 2f, size[1] / 2f) == null, at + "centre of screen is not a control");
        }
        // Diagonals can be turned off.
        Settings four = new Settings(); four.diagonals = false;
        ControlsLayout l4 = new ControlsLayout(2400, 1080, four, false);
        ControlsLayout.Item d4 = l4.find(ControlsLayout.DPAD);
        int k = l4.dpadKeys(d4, d4.cx + d4.radius() * .6f, d4.cy - d4.radius() * .6f);
        check(k == Keys.UP || k == Keys.RIGHT, "4-way: a diagonal push gives one direction");
        // Arena buttons can be hidden.
        Settings noArena = new Settings(); noArena.arenaButtons = false;
        check(new ControlsLayout(2400, 1080, noArena, false).find("ball") == null, "arena buttons hidden");
        // Edit mode swaps the gear for DONE/RESET.
        ControlsLayout ed = new ControlsLayout(2400, 1080, s, true);
        check(ed.find("gear") == null && ed.find("done") != null && ed.find("reset") != null, "edit mode buttons");
        // Moved positions and settings survive a round trip.
        Settings m = new Settings();
        m.style = 3; m.opacity = 0.5f; m.scale = 1.3f; m.haptics = false; m.arenaButtons = false; m.diagonals = false;
        m.positions.put("a", new float[] {0.9f, 0.5f});
        Settings back = Settings.parse(m.serialize());
        check(back.style == 3 && back.opacity == 0.5f && back.scale == 1.3f && !back.haptics
                && !back.arenaButtons && !back.diagonals, "settings round trip");
        ControlsLayout moved = new ControlsLayout(2000, 1000, back, false);
        check(Math.abs(moved.find("a").cx - 1800) < 0.5f && Math.abs(moved.find("a").cy - 500) < 0.5f, "moved A applied");
        // Garbage never throws, and out-of-range values are clamped.
        Settings junk = Settings.parse("style=99;opacity=7;scale=-3;pos.a=zz;nonsense");
        check(junk.style == Settings.MATCH_THEME && junk.opacity == 1f && junk.scale == 0.7f, "junk clamps");
        check(Themes.forBackground(4) == 4 && Themes.forBackground(42) == -1, "theme lookup");

        System.out.println(failures == 0 ? "ALL CONTROLS TESTS PASSED" : failures + " FAILURES");
        System.exit(failures == 0 ? 0 : 1);
    }
}
