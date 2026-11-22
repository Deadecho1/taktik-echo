package taktik.phone;

import java.io.ByteArrayOutputStream;
import java.lang.reflect.Method;
import java.util.Base64;
import java.util.Timer;
import java.util.TimerTask;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/** A scoped read using the installed UIAutomator2 hierarchy writer. */
public final class HierarchyReader {
    private static Object call(Object target, String name, Class<?>[] types, Object... args) throws Exception {
        Class<?> cls = target instanceof Class ? (Class<?>) target : target.getClass();
        Method method = cls.getMethod(name, types);
        return method.invoke(target instanceof Class ? null : target, args);
    }

    private static Object call(Object target, String name) throws Exception {
        return call(target, name, new Class<?>[0]);
    }

    private static String string(Object value) {
        return value == null ? "" : value.toString();
    }

    private static String bounds(Object node, int width, int height) throws Exception {
        Class<?> cls = Class.forName("android.graphics.Rect");
        Object rect = cls.getConstructor().newInstance();
        call(node, "getBoundsInScreen", new Class<?>[] {cls}, rect);
        int left = Math.max(0, cls.getField("left").getInt(rect));
        int top = Math.max(0, cls.getField("top").getInt(rect));
        int right = Math.min(width, cls.getField("right").getInt(rect));
        int bottom = Math.min(height, cls.getField("bottom").getInt(rect));
        return "[" + left + "," + top + "][" + right + "," + bottom + "]";
    }

    private static void attributes(Object node, Document document, int width, int height, int depth, int[] count) throws Exception {
        if (depth > 100 || ++count[0] > 5000) throw new IllegalStateException("Native node limit exceeded");
        boolean scrollable = Boolean.TRUE.equals(call(node, "isScrollable"));
        String text = string(call(node, "getText"));
        String locationKey = "android.view.accessibility.extra.DATA_TEXT_CHARACTER_LOCATION_KEY";
        boolean characters = !text.isEmpty() && text.length() <= 20000
            && string(call(node, "getAvailableExtraData")).contains(locationKey);
        if (characters) {
            String cls = string(call(node, "getClassName"));
            String id = string(call(node, "getViewIdResourceName"));
            String description = string(call(node, "getContentDescription"));
            String rect = bounds(node, width, height);
            NodeList candidates = document.getElementsByTagName("node");
            Element match = null;
            int matches = 0;
            for (int i = 0; i < candidates.getLength(); i++) {
                Element candidate = (Element) candidates.item(i);
                if (candidate.getAttribute("class").equals(cls)
                    && candidate.getAttribute("resource-id").equals(id)
                    && candidate.getAttribute("text").equals(text)
                    && candidate.getAttribute("content-desc").equals(description)
                    && candidate.getAttribute("scrollable").equals(Boolean.toString(scrollable))
                    && candidate.getAttribute("bounds").equals(rect)) {
                    match = candidate;
                    matches++;
                }
            }
            if (matches == 1) {
                if (characters) {
                    Class<?> bundleClass = Class.forName("android.os.Bundle");
                    Object args = bundleClass.getConstructor().newInstance();
                    call(args, "putInt", new Class<?>[] {String.class, int.class},
                        "android.view.accessibility.extra.DATA_TEXT_CHARACTER_LOCATION_ARG_START_INDEX", 0);
                    call(args, "putInt", new Class<?>[] {String.class, int.class},
                        "android.view.accessibility.extra.DATA_TEXT_CHARACTER_LOCATION_ARG_LENGTH", text.length());
                    boolean refreshed = Boolean.TRUE.equals(call(node, "refreshWithExtraData",
                        new Class<?>[] {String.class, bundleClass}, locationKey, args));
                    if (refreshed && text.equals(string(call(node, "getText"))) && rect.equals(bounds(node, width, height))) {
                        Object[] locations = (Object[]) call(call(node, "getExtras"), "getParcelableArray",
                            new Class<?>[] {String.class}, locationKey);
                        if (locations != null && locations.length == text.length()) {
                            StringBuilder positions = new StringBuilder();
                            for (Object location : locations) {
                                if (positions.length() > 0) positions.append(';');
                                if (location == null) positions.append("null");
                                else {
                                    Class<?> locationClass = location.getClass();
                                    positions.append(locationClass.getField("left").getFloat(location)).append(',')
                                        .append(locationClass.getField("top").getFloat(location)).append(',')
                                        .append(locationClass.getField("right").getFloat(location)).append(',')
                                        .append(locationClass.getField("bottom").getFloat(location));
                                }
                            }
                            match.setAttribute("taktik-character-locations", positions.toString());
                        }
                    }
                }
            }
        }
        int children = (Integer) call(node, "getChildCount");
        for (int i = 0; i < children; i++) {
            Object child = call(node, "getChild", new Class<?>[] {int.class}, i);
            if (child == null) continue;
            try { attributes(child, document, width, height, depth + 1, count); }
            finally { call(child, "recycle"); }
        }
    }

    private static String annotate(String xml, Object automation, Object device) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setExpandEntityReferences(false);
        Document document = factory.newDocumentBuilder().parse(
            new java.io.ByteArrayInputStream(xml.getBytes("UTF-8")));
        document.getDocumentElement().setAttribute("taktik-reader", "screen-reader");
        Object root = call(automation, "getRootInActiveWindow");
        if (root == null) throw new IllegalStateException("No active accessibility window");
        try {
            attributes(root, document, (Integer) call(device, "getDisplayWidth"),
                (Integer) call(device, "getDisplayHeight"), 0, new int[] {0});
        } finally { call(root, "recycle"); }
        java.io.StringWriter output = new java.io.StringWriter();
        TransformerFactory.newInstance().newTransformer().transform(new DOMSource(document), new StreamResult(output));
        return output.toString();
    }

    private static String read() throws Exception {
        Class<?> wrapperClass = Class.forName("uiautomator.InstrumentShellWrapper");
        Object wrapper = call(wrapperClass, "getInstance");
        Object automation = null;
        try {
            // The installed UIAutomator bridge owns main-Looper initialization.
            // Resolve its context before Android 16 starts accessibility callbacks.
            call(wrapper, "getContext");
            Class<?> deviceClass = Class.forName("androidx.test.uiautomator.UiDevice");
            Object device = call(deviceClass, "getInstance",
                new Class<?>[] {Class.forName("android.app.Instrumentation")}, wrapper);
            automation = call(device, "getUiAutomation");
            Object config = call(Class.forName("androidx.test.uiautomator.Configurator"), "getInstance");
            call(config, "setWaitForIdleTimeout", new Class<?>[] {long.class}, 0L);
            Object info = call(automation, "getServiceInfo");
            if (info == null) throw new IllegalStateException("Accessibility service is unavailable");
            Class<?> infoClass = info.getClass();
            int original = infoClass.getField("flags").getInt(info);
            String xml;
            try {
                // Include all windows and request the native screen-reader semantics.
                infoClass.getField("flags").setInt(info, original | 0x56);
                call(automation, "setServiceInfo", new Class<?>[] {infoClass}, info);
                Thread.sleep(750);
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                call(Class.forName("com.wetest.uia2.stub.AccessibilityNodeInfoDumper"), "dumpWindowHierarchy",
                    new Class<?>[] {deviceClass, java.io.OutputStream.class, int.class}, device, bytes, 100);
                xml = annotate(bytes.toString("UTF-8"), automation, device);
            } finally {
                infoClass.getField("flags").setInt(info, original);
                call(automation, "setServiceInfo", new Class<?>[] {infoClass}, info);
                Object restored = call(automation, "getServiceInfo");
                if (restored == null || infoClass.getField("flags").getInt(restored) != original) {
                    throw new IllegalStateException("Accessibility flags were not restored");
                }
            }
            return xml;
        } finally {
            try {
                if (automation != null) call(automation, "disconnect");
            } finally {
                call(wrapper, "destroy");
            }
        }
    }

    public static void main(String[] args) {
        // Process death also releases Android's temporary automation service.
        Timer watchdog = new Timer(true);
        watchdog.schedule(new TimerTask() {
            public void run() { Runtime.getRuntime().halt(2); }
        }, 10000);
        int status = 1;
        try {
            String xml = read();
            System.out.println("TAKTIK_HIERARCHY_V1:" + Base64.getEncoder().encodeToString(xml.getBytes("UTF-8")));
            status = 0;
        } catch (Throwable error) {
            error.printStackTrace(System.err);
        } finally {
            watchdog.cancel();
        }
        System.exit(status);
    }
}
