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
        check(Themes.ALL[Themes.forBackground(4)].id.equals("magma") && Themes.forBackground(99) == -1, "theme lookup");

        // ---- press animation ----
        ControlsLayout al = new ControlsLayout(2400, 1080, new Settings(), false);
        ControlsAnimator an = new ControlsAnimator();
        long t = 0, ms = 1_000_000L;
        an.step(al, 0, t);
        for (int i = 0; i < 5; i++) an.step(al, Keys.A | Keys.RIGHT, t += 16 * ms);   // 80ms held
        check(an.travel("a") > 0.9f && an.travel("a") < 1.05f, "A travels down within 80ms (" + an.travel("a") + ")");
        check(an.tiltX() > 0.9f && Math.abs(an.tiltY()) < 0.05f, "D-pad tilts right");
        float lowest = 1f;
        int settledAt = -1;
        for (int i = 0; i < 40; i++) {
            an.step(al, 0, t += 16 * ms);
            lowest = Math.min(lowest, an.travel("a"));
            if (settledAt < 0 && !an.animating()) settledAt = i;
        }
        check(lowest < 0f, "release overshoots its rest (bounces): " + lowest);
        check(settledAt > 0 && settledAt * 16 < 400, "release settles within 400ms (" + settledAt * 16 + "ms)");
        check(Math.abs(an.travel("a")) < 0.01f && Math.abs(an.tiltX()) < 0.01f, "back at rest");
        for (int i = 0; i < 10; i++) an.step(al, Keys.UP | Keys.LEFT, t += 16 * ms);
        check(Math.abs(an.tiltX() + 0.707f) < 0.05f && Math.abs(an.tiltY() + 0.707f) < 0.05f, "diagonal splits the tilt");
        an.step(al, Keys.UP | Keys.LEFT, t += 5_000 * ms);   // a long stall (app paused) stays stable
        check(Math.abs(an.tiltX() + 0.707f) < 0.05f && !Float.isNaN(an.tiltX()), "long frame gap is stable");

        // ---- handheld themes ----
        int kyogre = Themes.indexOf("handheld_kyogre");
        Settings sh = new Settings(); sh.shellTheme = kyogre;
        check(Settings.parse(sh.serialize()).shellTheme == kyogre, "shell theme round trip (by id)");
        check(Settings.parse("shellId=rain").shellTheme == -1, "a non-shell theme id is rejected");
        check(Settings.parse("shellId=nope").shellTheme == -1, "an unknown theme id is rejected");
        // Settings saved before ids stored an index into the old list: 9 was Indigo, 16 Emerald.
        check(Themes.ALL[Settings.parse("shell=9").shellTheme].id.equals("handheld_indigo"), "legacy shell 9 -> Indigo");
        check(Themes.ALL[Settings.parse("shell=16").shellTheme].id.equals("handheld_emerald"), "legacy shell 16 -> Emerald");
        check(Settings.parse("shell=2").shellTheme == -1, "legacy non-shell index is rejected");
        int shells = 0;
        for (Themes th : Themes.ALL) if (th.isShell()) { shells++; check(ButtonStyle.ALL[th.style].gba, th.name + " uses a hardware style"); }
        check(shells == 12, "twelve handheld shells (" + shells + ")");
        check(Themes.forBackground(Themes.SHELL) == -1, "shell is never matched as an image background");
        // A handheld is a theme, not a button style: a stored handheld style
        // (possible in older versions) would give its buttons with no body.
        check(Settings.parse("style=8").style == Settings.MATCH_THEME, "handheld button style is not kept");
        check(Settings.parse("style=21").style == Settings.MATCH_THEME, "new handheld button style is not kept");
        check(Settings.parse("style=16").style == 16, "a flat style is kept");

        // ---- the catalogue ----
        java.util.Set<String> ids = new java.util.HashSet<>();
        java.util.Set<Integer> bgs = new java.util.HashSet<>();
        java.util.Set<String> cats = new java.util.HashSet<>(java.util.Arrays.asList(Themes.CATEGORIES));
        int listed = 0;
        for (String c : Themes.CATEGORIES) {
            check(!Themes.in(c).isEmpty(), "category " + c + " has themes");
            listed += Themes.in(c).size();
        }
        check(listed == Themes.ALL.length, "every theme is in exactly one gallery category");
        for (Themes th : Themes.ALL) {
            check(ids.add(th.id), "theme id unique: " + th.id);
            check(cats.contains(th.category), th.name + " has a known category");
            check(th.style >= 0 && th.style < ButtonStyle.ALL.length, th.name + " style index valid");
            if (!th.isShell()) {
                check(bgs.add(th.background), "background number unique: " + th.background);
                check(th.background >= 0 && th.background < 64, th.name + " background within the game's limit");
                check(!ButtonStyle.ALL[th.style].gba, th.name + " (an image theme) matches a flat style");
            }
        }
        for (int i = 0; i < bgs.size(); i++) check(bgs.contains(i), "background numbers have no gap at " + i);
        check(ButtonStyle.ALL.length == 25, "25 button styles (" + ButtonStyle.ALL.length + ")");

        // ---- every style renders, with and without shell and animation ----
        java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(1200, 540, java.awt.image.BufferedImage.TYPE_INT_ARGB);
        for (ButtonStyle st : ButtonStyle.ALL) {
            for (boolean edit : new boolean[] {false, true}) {
                try {
                    java.awt.Graphics2D g = img.createGraphics();
                    ControlsLayout rl = new ControlsLayout(1200, 540, new Settings(), edit);
                    ControlsRenderer.draw(new AwtPainter(g), rl, st, 0.8f, Keys.A | Keys.UP, an, st.gba);
                    g.dispose();
                } catch (RuntimeException e) {
                    check(false, st.name + " render threw " + e);
                }
            }
        }
        // every gallery card draws, "None" included
        java.awt.image.BufferedImage cardImg = new java.awt.image.BufferedImage(ThemeCard.W, ThemeCard.H,
                java.awt.image.BufferedImage.TYPE_INT_ARGB);
        java.util.List<Themes> withNone = new java.util.ArrayList<>(java.util.Arrays.asList(Themes.ALL));
        withNone.add(null);
        for (Themes th : withNone) {
            try {
                java.awt.Graphics2D g = cardImg.createGraphics();
                ThemeCard.drawOver(new AwtPainter(g), th);
                g.dispose();
            } catch (RuntimeException e) {
                check(false, (th == null ? "None" : th.name) + " card threw " + e);
            }
        }
        // the shell never paints inside the game rectangle
        ControlsLayout gl = new ControlsLayout(1200, 540, new Settings(), false);
        java.awt.image.BufferedImage shellImg = new java.awt.image.BufferedImage(1200, 540, java.awt.image.BufferedImage.TYPE_INT_ARGB);
        java.awt.Graphics2D sg = shellImg.createGraphics();
        ControlsRenderer.drawShellForTest(new AwtPainter(sg), gl, ButtonStyle.ALL[8]);
        sg.dispose();
        int painted = 0;
        for (int y = gl.gameT; y < gl.gameB; y += 3)
            for (int x = gl.gameL; x < gl.gameR; x += 3)
                if ((shellImg.getRGB(x, y) >>> 24) != 0) painted++;
        check(painted == 0, "shell leaves the game rectangle untouched (" + painted + " px painted)");

        // Every flat style's ink reads on every face it is drawn on.
        for (ButtonStyle st : ButtonStyle.ALL) {
            if (st.gba) continue;
            for (int face : new int[] {st.face, st.pressed, st.dpad, st.accentA, st.accentB}) {
                if (face == 0) continue;
                double c = ControlsRenderer.contrast(ControlsRenderer.inkOn(st, face), ControlsRenderer.seenFace(st, face));
                check(c >= 3.0, st.name + " ink on " + Integer.toHexString(face) + " contrast " + c);
            }
        }
        System.out.println(failures == 0 ? "ALL CONTROLS TESTS PASSED" : failures + " FAILURES");
        System.exit(failures == 0 ? 0 : 1);
    }
}
