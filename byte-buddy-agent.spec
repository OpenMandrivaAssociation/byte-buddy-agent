Name:		byte-buddy-agent
Version:	1.18.17
Release:	1
Summary:	Java agent that attaches Byte Buddy to a running virtual machine
Group:		Development/Java
License:	Apache-2.0
URL:		https://bytebuddy.net
Source0:	https://codeload.github.com/raphw/byte-buddy/tar.gz/refs/tags/byte-buddy-%{version}#/byte-buddy-%{version}.tar.gz
BuildArch:	noarch
BuildRequires:	java-current-devel
BuildRequires:	python
BuildRequires:	sysjar
BuildRequires:	mvn(net.java.dev.jna:jna)
BuildRequires:	mvn(net.java.dev.jna:jna-platform)

%description
Attaches a Java agent to the current or another virtual machine. The
default path uses the JDK attach API. Java Native Access is only needed
to compile the optional emulator and is not required at runtime.

%prep
%setup -q -n byte-buddy-byte-buddy-%{version}
find . -name '*.class' -delete
find . -name '*.jar' -delete
find . -name '*.dll' -delete
rm -rf byte-buddy byte-buddy-dep byte-buddy-android byte-buddy-android-test \
	byte-buddy-benchmark byte-buddy-fuzz byte-buddy-gradle-plugin \
	byte-buddy-maven-plugin
if find . \( -name '*.class' -o -name '*.jar' -o -name '*.dll' \) | grep -q .; then
	echo "prebuilt bytecode remains" >&2
	exit 1
fi

%build
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java}"
mkdir -p build/stub build/stub-classes build/classes
python - << 'PY'
from pathlib import Path
files = {
    "build/stub/edu/umd/cs/findbugs/annotations/SuppressFBWarnings.java": """
package edu.umd.cs.findbugs.annotations;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.TYPE, ElementType.FIELD, ElementType.METHOD, ElementType.PARAMETER, ElementType.CONSTRUCTOR, ElementType.LOCAL_VARIABLE, ElementType.PACKAGE})
public @interface SuppressFBWarnings {
	String[] value() default {};
	String justification() default "";
}
""",
    "build/stub/javax/annotation/meta/When.java": """
package javax.annotation.meta;
public enum When { ALWAYS, UNKNOWN, MAYBE, NEVER }
""",
    "build/stub/javax/annotation/Nonnull.java": """
package javax.annotation;
import javax.annotation.meta.When;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.METHOD, ElementType.PARAMETER, ElementType.FIELD, ElementType.TYPE, ElementType.PACKAGE})
public @interface Nonnull {
	When when() default When.ALWAYS;
}
""",
    "build/stub/javax/annotation/meta/TypeQualifierNickname.java": """
package javax.annotation.meta;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Retention(RetentionPolicy.SOURCE)
@Target(ElementType.ANNOTATION_TYPE)
public @interface TypeQualifierNickname {}
""",
    "build/stub/javax/annotation/meta/TypeQualifierDefault.java": """
package javax.annotation.meta;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Retention(RetentionPolicy.SOURCE)
@Target(ElementType.ANNOTATION_TYPE)
public @interface TypeQualifierDefault {
	ElementType[] value();
}
""",
}
for name, text in files.items():
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
PY
find build/stub -name '*.java' > build/stub-sources.list
"$JAVA_HOME/bin/javac" --release 8 -encoding UTF-8 -d build/stub-classes @build/stub-sources.list
find byte-buddy-agent/src/main/java -name '*.java' > build/sources.list
test "$(wc -l < build/sources.list)" -eq 10
"$JAVA_HOME/bin/javac" --release 8 -encoding UTF-8 \
	-cp "build/stub-classes:/usr/share/java/jna.jar:/usr/share/java/jna-platform.jar" \
	-d build/classes @build/sources.list
python - build/classes << 'PY'
import os
import sys
root = sys.argv[1]
count = 0
for dirpath, _, files in os.walk(root):
    for name in files:
        if not name.endswith(".class"):
            continue
        count += 1
        rel = os.path.join(dirpath, name)
        if "findbugs" in rel or "javax/annotation" in rel:
            raise SystemExit("stub class was packaged: " + rel)
        data = open(rel, "rb").read(8)
        major = int.from_bytes(data[6:8], "big")
        if major != 52:
            raise SystemExit("class " + name + " has major " + str(major))
if count != 71:
    raise SystemExit("class count " + str(count))
PY
cat > build/manifest.mf << EOF
Manifest-Version: 1.0
Premain-Class: net.bytebuddy.agent.Installer
Agent-Class: net.bytebuddy.agent.Installer
Can-Redefine-Classes: true
Can-Retransform-Classes: true
Can-Set-Native-Method-Prefix: true
Implementation-Title: net.bytebuddy.agent
Implementation-Version: %{version}
Automatic-Module-Name: net.bytebuddy.agent

EOF
"$JAVA_HOME/bin/jar" --create --manifest build/manifest.mf \
	--file build/byte-buddy-agent.jar -C build/classes .
cat > build/byte-buddy-agent.pom << EOF
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.bytebuddy</groupId>
  <artifactId>byte-buddy-agent</artifactId>
  <version>%{version}</version>
  <name>Byte Buddy agent</name>
  <description>Attaches a Java agent. JNA is optional and is not required when the JDK attach API is available.</description>
  <url>https://bytebuddy.net</url>
  <licenses>
    <license><name>Apache-2.0</name></license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>net.java.dev.jna</groupId>
      <artifactId>jna</artifactId>
      <version>5.19.1</version>
      <scope>provided</scope>
      <optional>true</optional>
    </dependency>
    <dependency>
      <groupId>net.java.dev.jna</groupId>
      <artifactId>jna-platform</artifactId>
      <version>5.19.1</version>
      <scope>provided</scope>
      <optional>true</optional>
    </dependency>
  </dependencies>
</project>
EOF

%install
sysjar install --buildroot %{buildroot} \
	--artifact build/byte-buddy-agent.pom:build/byte-buddy-agent.jar \
	--file-name byte-buddy-agent \
	--filelist .mfiles

%check
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java}"
"$JAVA_HOME/bin/jar" tf build/byte-buddy-agent.jar > build/jar-list.txt
grep -qx 'net/bytebuddy/agent/ByteBuddyAgent.class' build/jar-list.txt
grep -qx 'net/bytebuddy/agent/Installer.class' build/jar-list.txt
grep -qx 'net/bytebuddy/agent/Attacher.class' build/jar-list.txt
if grep -E 'findbugs|javax/annotation|\.dll$|module-info' build/jar-list.txt; then
	echo "jar contains a stub, a native library, or module-info" >&2
	exit 1
fi
"$JAVA_HOME/bin/jar" --describe-module --file build/byte-buddy-agent.jar > build/module.txt
grep -F 'net.bytebuddy.agent automatic' build/module.txt
cat > build/Probe.java << 'EOF'
import java.lang.instrument.Instrumentation;
import net.bytebuddy.agent.ByteBuddyAgent;

public class Probe {
    public static void main(String[] args) {
        Instrumentation instrumentation = ByteBuddyAgent.install();
        if (instrumentation == null || !instrumentation.isRetransformClassesSupported()) {
            throw new AssertionError("agent did not install");
        }
        System.out.println("probe ok");
    }
}
EOF
"$JAVA_HOME/bin/javac" --release 8 -encoding UTF-8 \
	-cp build/byte-buddy-agent.jar \
	-d build build/Probe.java
"$JAVA_HOME/bin/java" --enable-native-access=ALL-UNNAMED \
	-cp "build:build/byte-buddy-agent.jar" \
	Probe > build/probe.txt
cat build/probe.txt
grep -qx 'probe ok' build/probe.txt

%files -f .mfiles
%license LICENSE NOTICE
%doc README.md release-notes.md
