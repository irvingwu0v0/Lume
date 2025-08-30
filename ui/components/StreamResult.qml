import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

// Streaming AI output panel: title + status + collapsible reasoning +
// auto-scrolling main content. Pages drive it via begin/appendChunk/
// finish/fail and read `content` for exporting.
Frame {
    id: root
    Layout.fillWidth: true
    padding: 20

    property string title: qsTr("生成结果")
    property string status: ""
    property bool generating: false
    property bool thinkExpanded: true
    property bool autoScroll: true

    readonly property string content: _content
    readonly property string thinking: _thinking

    property string _content: ""
    property string _thinking: ""
    property string _contentBuffer: ""
    property string _thinkingBuffer: ""

    signal stopRequested()

    function reset() {
        flushTimer.stop()
        _content = ""
        _thinking = ""
        _contentBuffer = ""
        _thinkingBuffer = ""
        generating = false
        status = ""
    }

    function begin(pendingText) {
        reset()
        generating = true
        status = pendingText !== undefined ? pendingText : qsTr("正在等待 AI 响应...")
    }

    function flushBuffers() {
        if (_contentBuffer) { _content += _contentBuffer; _contentBuffer = "" }
        if (_thinkingBuffer) { _thinking += _thinkingBuffer; _thinkingBuffer = "" }
    }

    function appendChunk(chunk) {
        try {
            var obj = JSON.parse(chunk)
            if (obj.reasoning) {
                _thinkingBuffer += obj.reasoning
                status = qsTr("AI 正在思考...")
            }
            if (obj.content) {
                _contentBuffer += obj.content
                status = qsTr("AI 正在生成...")
            }
            if (!flushTimer.running) flushTimer.restart()
        } catch (e) {}
    }

    function finish(fullText) {
        flushTimer.stop()
        flushBuffers()
        _content = fullText
        generating = false
        status = qsTr("生成完成")
    }

    function fail() {
        flushTimer.stop()
        flushBuffers()
        generating = false
        status = qsTr("生成出错")
    }

    Timer {
        id: flushTimer
        interval: 80
        repeat: false
        onTriggered: root.flushBuffers()
    }

    ColumnLayout {
        width: parent.width
        spacing: 12

        RowLayout {
            Text {
                text: root.title
                typography: Typography.BodyStrong
            }
            BusyIndicator {
                visible: root.generating
                running: visible
                implicitWidth: 18
                implicitHeight: 18
            }
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("停止")
                flat: true
                visible: root.generating
                onClicked: root.stopRequested()
            }
        }

        Text {
            text: root.status
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
        }

        // Thinking process (collapsible, 200px max, auto-scroll)
        Frame {
            visible: root.thinking !== ""
            Layout.fillWidth: true
            padding: 12

            ColumnLayout {
                width: parent.width
                spacing: 4

                RowLayout {
                    Text {
                        text: qsTr("思考过程")
                        font.pixelSize: 12; font.bold: true
                        color: Theme.currentTheme.colors.primaryColor
                    }
                    Item { Layout.fillWidth: true }
                    RoundButton {
                        implicitWidth: 28; implicitHeight: 28
                        icon.name: root.thinkExpanded
                            ? "ic_fluent_chevron_up_20_regular"
                            : "ic_fluent_chevron_down_20_regular"
                        flat: true
                        onClicked: root.thinkExpanded = !root.thinkExpanded
                    }
                }

                Flickable {
                    visible: root.thinkExpanded
                    Layout.fillWidth: true
                    implicitHeight: Math.min(thinkText.implicitHeight, 200)
                    contentHeight: thinkText.implicitHeight
                    clip: true
                    onContentHeightChanged: contentY = contentHeight - height

                    Text {
                        id: thinkText
                        width: parent.width
                        text: root.thinking
                        font.pixelSize: 12
                        color: Theme.currentTheme.colors.textSecondaryColor
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // Main content (300px, auto-scroll)
        Frame {
            Layout.fillWidth: true
            implicitHeight: 300
            padding: 12

            Flickable {
                anchors.fill: parent
                contentHeight: resultText.implicitHeight
                clip: true
                onContentHeightChanged: contentY = contentHeight - height

                Text {
                    id: resultText
                    width: parent.width
                    text: root.content
                    wrapMode: Text.WordWrap
                    typography: Typography.Body
                }
            }
        }
    }
}
