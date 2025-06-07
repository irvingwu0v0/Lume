import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

FluentPage {
    id: root
    title: qsTr("作文思路生成")
    horizontalPadding: 56
    layer.enabled: false

    property int currentStep: 1
    property string inputText: ""
    property string writeMode: "continuation"
    property string selectedModelId: ""
    property bool selectedModelThinking: false
    property string fullContent: ""
    property string thinkingContent: ""
    property bool isGenerating: false
    property bool thinkExpanded: true
    property string resultStatus: ""

    property string _contentBuffer: ""
    property string _thinkingBuffer: ""

    Timer {
        id: flushTimer
        interval: 80
        repeat: false
        onTriggered: {
            if (_contentBuffer) { fullContent += _contentBuffer; _contentBuffer = "" }
            if (_thinkingBuffer) { thinkingContent += _thinkingBuffer; _thinkingBuffer = "" }
        }
    }

    // ── 模型数据 ──
    ListModel { id: writingModelList }

    function stepColor(s) {
        if (s < currentStep) return Theme.currentTheme.colors.successColor
        if (s === currentStep) return Theme.currentTheme.colors.primaryColor
        return Theme.currentTheme.colors.controlBorderStrongColor
    }

    function reloadModels() {
        writingModelList.clear()
        modelCombo.data = []
        try {
            var m = JSON.parse(api.getModelsJson())
            modelCombo.data = m
            for (var i = 0; i < m.length; i++) {
                var label = m[i].alias
                if (m[i].thinking_enabled) label += " [思考]"
                if (m[i].vision_enabled) label += " [视觉]"
                writingModelList.append({ text: label })
            }
            modelCombo.currentIndex = -1
            modelCombo.currentIndex = 0
        } catch (e) {}
    }

    // ── 步骤指示器 ──
    Frame {
        Layout.fillWidth: true
        padding: 16

        RowLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 0

            Repeater {
                model: [
                    { label: qsTr("输入题目"), step: 1 },
                    { label: qsTr("选择模型"), step: 2 },
                    { label: qsTr("结果导出"), step: 3 }
                ]

                Item {
                    Layout.fillWidth: true
                    implicitHeight: childrenRect.height

                    Rectangle {
                        id: dot
                        anchors.horizontalCenter: parent.horizontalCenter
                        implicitWidth: 28; implicitHeight: 28; radius: 14
                        color: stepColor(modelData.step)
                        Text {
                            anchors.centerIn: parent
                            color: "white"; font.pixelSize: 11; font.bold: true
                            text: modelData.step < currentStep ? "\u2713" : modelData.step
                        }
                    }
                    Text {
                        anchors.top: dot.bottom; anchors.topMargin: 4
                        anchors.horizontalCenter: dot.horizontalCenter
                        text: modelData.label; typography: Typography.Caption
                        color: modelData.step === currentStep
                            ? Theme.currentTheme.colors.primaryColor
                            : Theme.currentTheme.colors.textSecondaryColor
                    }
                    Rectangle {
                        visible: index < 2
                        anchors.left: dot.right; anchors.leftMargin: 4
                        anchors.right: parent.right
                        anchors.verticalCenter: dot.verticalCenter
                        implicitHeight: 2; radius: 1
                        color: modelData.step < currentStep
                            ? Theme.currentTheme.colors.successColor
                            : Theme.currentTheme.colors.controlBorderStrongColor
                    }
                    Rectangle {
                        visible: index > 0
                        anchors.right: dot.left; anchors.rightMargin: 4
                        anchors.left: parent.left
                        anchors.verticalCenter: dot.verticalCenter
                        implicitHeight: 2; radius: 1
                        color: modelData.step <= currentStep
                            ? Theme.currentTheme.colors.successColor
                            : Theme.currentTheme.colors.controlBorderStrongColor
                    }
                }
            }
        }
    }

    // ── 步骤 1: 输入题目 ──
    Frame {
        visible: currentStep === 1
        Layout.fillWidth: true
        padding: 20

        ColumnLayout {
            width: parent.width
            spacing: 12

            Text {
                text: qsTr("输入作文题目")
                typography: Typography.BodyStrong
            }
            Text {
                text: writeMode === "continuation"
                    ? qsTr("读后续写模式 — 分析原文并生成续写思路")
                    : qsTr("应用文模式 — 分析题目并生成写作框架")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }

            TextArea {
                id: textArea
                Layout.fillWidth: true
                implicitHeight: 200
                placeholderText: writeMode === "continuation"
                    ? qsTr("在此粘贴阅读理解原文及续写提示句...")
                    : qsTr("在此粘贴应用文写作题目...")
                onTextChanged: inputText = text
            }

            RowLayout {
                spacing: 12
                Text {
                    text: qsTr("写作模式：")
                    typography: Typography.Body
                }
                RadioButton {
                    text: qsTr("读后续写")
                    checked: writeMode === "continuation"
                    onCheckedChanged: if (checked) writeMode = "continuation"
                }
                RadioButton {
                    text: qsTr("应用文")
                    checked: writeMode === "practical"
                    onCheckedChanged: if (checked) writeMode = "practical"
                }
            }

            Button {
                text: qsTr("下一步：选择 AI 模型")
                highlighted: true
                enabled: inputText.trim().length > 0
                onClicked: {
                    reloadModels()
                    currentStep = 2
                }
            }
        }
    }

    // ── 步骤 2: 选择模型 ──
    Frame {
        visible: currentStep === 2
        Layout.fillWidth: true
        padding: 20

        ColumnLayout {
            width: parent.width
            spacing: 12

            Text {
                text: qsTr("选择 AI 模型")
                typography: Typography.BodyStrong
            }
            Text {
                text: qsTr("选择用于生成写作思路的 AI 模型")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }

            ComboBox {
                id: modelCombo
                Layout.fillWidth: true
                property var data: []
                model: writingModelList
                placeholderText: qsTr("请选择模型...")
                currentIndex: 0
                onCurrentIndexChanged: {
                    if (currentIndex >= 0 && currentIndex < data.length) {
                        var item = data[currentIndex]
                        selectedModelId = item.id
                        selectedModelThinking = item.thinking_enabled
                    }
                }
            }

            RowLayout {
                spacing: 12
                Button {
                    text: qsTr("上一步")
                    onClicked: {
                        api.cancelGeneration()
                        currentStep = 1
                    }
                }
                Button {
                    text: qsTr("确认，开始生成")
                    highlighted: true
                    enabled: selectedModelId !== ""
                    onClicked: {
                        currentStep = 3
                        isGenerating = true
                        fullContent = ""
                        thinkingContent = ""
                        _contentBuffer = ""
                        _thinkingBuffer = ""
                        flushTimer.stop()
                        resultStatus = qsTr("正在等待 AI 响应...")
                        api.startWritingGeneration(inputText, selectedModelId, selectedModelThinking, writeMode)
                    }
                }
            }

            Text {
                visible: writingModelList.count === 0
                text: qsTr("暂未配置模型，请先在「设置」页面添加 AI 模型")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }
        }
    }

    // ── 步骤 3: 结果 ──
    Frame {
        visible: currentStep === 3
        Layout.fillWidth: true
        padding: 20

        ColumnLayout {
            width: parent.width
            spacing: 12

            RowLayout {
                Text {
                    text: qsTr("生成结果")
                    typography: Typography.BodyStrong
                }
                BusyIndicator {
                    visible: isGenerating
                    running: visible
                    implicitWidth: 18
                    implicitHeight: 18
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: qsTr("停止")
                    flat: true
                    visible: isGenerating
                    onClicked: {
                        api.cancelGeneration()
                        isGenerating = false
                    }
                }
            }

            Text {
                text: resultStatus
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }

            // Thinking process (collapsible, 200px max, auto-scroll)
            Frame {
                visible: thinkingContent !== ""
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
                            icon.name: thinkExpanded ? "ic_fluent_chevron_up_20_regular" : "ic_fluent_chevron_down_20_regular"
                            flat: true
                            onClicked: thinkExpanded = !thinkExpanded
                        }
                    }

                    Flickable {
                        visible: thinkExpanded
                        Layout.fillWidth: true
                        implicitHeight: Math.min(thinkText.implicitHeight, 200)
                        contentHeight: thinkText.implicitHeight
                        clip: true
                        onContentHeightChanged: contentY = contentHeight - height

                        Text {
                            id: thinkText
                            width: parent.width
                            text: thinkingContent
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
                    id: resultFlick
                    anchors.fill: parent
                    contentHeight: resultText.implicitHeight
                    clip: true
                    onContentHeightChanged: contentY = contentHeight - height

                    Text {
                        id: resultText
                        width: parent.width
                        text: fullContent
                        wrapMode: Text.WordWrap
                        typography: Typography.Body
                    }
                }
            }

            RowLayout {
                spacing: 12
                visible: !isGenerating && fullContent.length > 0
                Button { text: qsTr("导出 Word"); highlighted: true
                onClicked: {
                    var r = JSON.parse(api.saveWritingDocx(fullContent, writeMode))
                    if (r.ok) floatLayer.createInfoBar({ severity: Severity.Success, title: qsTr("成功"), text: qsTr("Word 文档已保存"), timeout: 3000 })
                    else if (!r.cancelled) floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("导出失败"), text: r.error || "", timeout: 5000 })
                }
            }
            }

            Button {
                text: qsTr("上一步")
                onClicked: {
                    api.cancelGeneration()
                    isGenerating = false
                    currentStep = 2
                }
            }
        }
    }

    Connections {
        target: api
        function onWritingChunk(chunk) {
            try {
                var obj = JSON.parse(chunk)
                if (obj.reasoning) {
                    _thinkingBuffer += obj.reasoning
                    resultStatus = qsTr("AI 正在思考...")
                }
                if (obj.content) {
                    _contentBuffer += obj.content
                    resultStatus = qsTr("AI 正在生成...")
                }
                if (!flushTimer.running) flushTimer.restart()
            } catch (e) {}
        }
        function onWritingDone(content) {
            flushTimer.stop()
            if (_contentBuffer) { fullContent += _contentBuffer; _contentBuffer = "" }
            if (_thinkingBuffer) { thinkingContent += _thinkingBuffer; _thinkingBuffer = "" }
            fullContent = content
            isGenerating = false
            resultStatus = qsTr("生成完成")
        }
        function onWritingError(err) {
            flushTimer.stop()
            if (_contentBuffer) { fullContent += _contentBuffer; _contentBuffer = "" }
            if (_thinkingBuffer) { thinkingContent += _thinkingBuffer; _thinkingBuffer = "" }
            isGenerating = false
            resultStatus = qsTr("生成出错")
            floatLayer.createInfoBar({
                severity: Severity.Error,
                title: qsTr("错误"),
                text: err,
                timeout: 5000
            })
        }
    }
}
