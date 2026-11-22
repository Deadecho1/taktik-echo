"""Execute the production Java entry point against Android's Looper precondition."""

import base64
import os
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest
from unit.paths import CORE

SOURCES = {
    "android/os/Looper.java": """package android.os;
public class Looper {
    private static Object main = Boolean.getBoolean("fixture.prepared") ? new Object() : null;
    public static Object getMainLooper() { return main; }
    public static void prepareMainLooper() {
        if (main != null) throw new IllegalStateException("Main Looper already exists");
        main = new Object();
    }
}""",
    "android/app/Instrumentation.java": """package android.app;
public class Instrumentation { public Object getContext() { return null; } }""",
    "uiautomator/InstrumentShellWrapper.java": """package uiautomator;
public class InstrumentShellWrapper extends android.app.Instrumentation {
    private static Object context = Boolean.getBoolean("fixture.prepared") ? new Object() : null;
    public static InstrumentShellWrapper getInstance() { return new InstrumentShellWrapper(); }
    public Object getContext() {
        if (context == null) {
            android.os.Looper.prepareMainLooper();
            context = new Object();
        }
        return context;
    }
    public void destroy() { System.out.println("WRAPPER_DESTROYED"); }
}""",
    "androidx/test/uiautomator/UiDevice.java": """package androidx.test.uiautomator;
public class UiDevice {
    public static UiDevice getInstance(android.app.Instrumentation wrapper) {
        if (android.os.Looper.getMainLooper() == null)
            throw new IllegalStateException("Android accessibility requires the main Looper");
        wrapper.getContext();
        return new UiDevice();
    }
    public fixture.Automation getUiAutomation() { return new fixture.Automation(); }
    public int getDisplayWidth() { return 100; }
    public int getDisplayHeight() { return 100; }
}""",
    "androidx/test/uiautomator/Configurator.java": """package androidx.test.uiautomator;
public class Configurator {
    public static Configurator getInstance() { return new Configurator(); }
    public void setWaitForIdleTimeout(long timeout) {}
}""",
    "fixture/Automation.java": """package fixture;
public class Automation {
    public static class Info { public int flags = 1; }
    public static class Node {
        public boolean isScrollable() { return false; }
        public String getText() { return ""; }
        public int getChildCount() { return 0; }
        public void recycle() {}
    }
    private Info info = new Info();
    public Info getServiceInfo() { return info; }
    public void setServiceInfo(Info value) { info = value; }
    public Node getRootInActiveWindow() { return new Node(); }
    public void disconnect() {
        if (info.flags != 1) throw new IllegalStateException("Flags were not restored");
        System.out.println("AUTOMATION_DISCONNECTED");
    }
}""",
    "com/wetest/uia2/stub/AccessibilityNodeInfoDumper.java": """package com.wetest.uia2.stub;
public class AccessibilityNodeInfoDumper {
    public static void dumpWindowHierarchy(androidx.test.uiautomator.UiDevice device,
            java.io.OutputStream output, int depth) throws Exception {
        if (Boolean.getBoolean("fixture.failRead")) throw new IllegalStateException("Fixture read failure");
        output.write("<hierarchy><node package='fixture'/></hierarchy>".getBytes("UTF-8"));
    }
}""",
}


@pytest.fixture(scope="module")
def native_entrypoint(tmp_path_factory):
    jdk = os.environ.get("TAKTIK_TEST_JDK")
    javac = str(Path(jdk) / "bin/javac") if jdk else shutil.which("javac")
    java = str(Path(jdk) / "bin/java") if jdk else shutil.which("java")
    if not javac or not java:
        pytest.skip("A JDK is needed to execute the native Java entry point")
    work = tmp_path_factory.mktemp("native-entrypoint")
    files = []
    for name, content in SOURCES.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        files.append(str(path))
    source = CORE / "taktik/core/shared/phone_interaction/native/HierarchyReader.java"
    subprocess.run(
        [javac, "-d", str(work), str(source), *files],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [java, "-cp", str(work)]


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_native_main_initializes_looper_before_connecting_and_restores_lifetime(
    native_entrypoint, prepared, failure
):
    result = subprocess.run(
        [
            *native_entrypoint,
            f"-Dfixture.prepared={str(prepared).lower()}",
            f"-Dfixture.failRead={str(failure).lower()}",
            "taktik.phone.HierarchyReader",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    assert "AUTOMATION_DISCONNECTED" in result.stdout, result.stderr
    assert "WRAPPER_DESTROYED" in result.stdout, result.stderr
    records = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("TAKTIK_HIERARCHY_V1:")
    ]
    if failure:
        assert result.returncode == 1 and not records
        assert "Fixture read failure" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert len(records) == 1
        root = ElementTree.fromstring(base64.b64decode(records[0].split(":", 1)[1]))
        assert root.attrib["taktik-reader"] == "screen-reader"
