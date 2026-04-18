import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

FluentPage {
    id: root
    title: qsTr("试卷转换")
    horizontalPadding: 56
    layer.enabled: false

    property int currentStep: 1
    property string uploadMode: "pdf"  // "pdf" | "phone"

    // PDF mode properties
    property string pdfFile: ""
    property string pdfFileName: ""
    property string pdfMode: "ocr"
    property bool batchMode: false
    property bool phoneWaiting: false
    property bool splitMode: false
    property bool visionMode: false

    // Phone mode properties
    property bool phoneConnected: false
    property int phoneImageCount: 0
    property string phoneLanIp: ""
    property string phoneNetworkName: ""
    property bool phoneServerStarting: false

    // Common AI/model properties
    property string selectedModelId: ""
    property bool selectedModelThinking: false
    property int ocrProgress: 0
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

    ListModel { id: pdfModelList }
    ListModel { id: phoneImageModel }

    function stepColor(s) {
        if (s < currentStep) return Theme.currentTheme.colors.successColor
        if (s === currentStep) return Theme.currentTheme.colors.primaryColor
        return Theme.currentTheme.colors.controlBorderStrongColor
    }

    function reloadPdfModels() {
        pdfModelList.clear()
        modelCombo.data = []
        try {
            var m = JSON.parse(api.getModelsJson())
            var filtered = []
            for (var i = 0; i < m.length; i++) {
                if (pdfMode === "vision" && !m[i].vision_enabled) continue
                filtered.push(m[i])
            }
            modelCombo.data = filtered
            for (var j = 0; j < filtered.length; j++) {
                var label = filtered[j].alias
                if (filtered[j].thinking_enabled) label += " [思考]"
                if (filtered[j].vision_enabled) label += " [视觉]"
                pdfModelList.append({ text: label })
            }
            modelCombo.currentIndex = -1
            modelCombo.currentIndex = 0
        } catch (e) {}
    }

    function startPhoneConnection() {
        phoneServerStarting = true
        phoneImageModel.clear()
        phoneImageCount = 0
        phoneConnected = false
        phoneLanIp = api.getPhoneLanIp()
        phoneNetworkName = api.getPhoneNetworkName()
        var ok = api.startPhoneServer()
        phoneServerStarting = false
        if (!ok) {
            floatLayer.createInfoBar({
                severity: Severity.Error,
                title: qsTr("连接服务启动失败"),
                text: qsTr("端口 18923 可能被占用，请关闭其他 Lume 实例后重试"),
                timeout: 5000
            })
        }
    }

    function stopPhoneConnection() {
        api.stopPhoneServer()
        phoneConnected = false
        phoneImageCount = 0
        phoneImageModel.clear()
        phoneLanIp = ""
        phoneNetworkName = ""
    }

    function movePhoneImageLocally(from, to) {
        if (from < 0 || from >= phoneImageCount || to < 0 || to >= phoneImageCount || from === to) return
        api.movePhoneImage(from, to)
    }

    function deletePhoneImageLocally(index) {
        if (index < 0 || index >= phoneImageCount) return
        api.deletePhoneImage(index)
    }

    function rebuildPhoneModel() {
        // Rebuild the model from fresh temp files when images change.
        phoneImageModel.clear()
        phoneImageCount = 0
    }

    onUploadModeChanged: {
        if (uploadMode === "phone") {
            startPhoneConnection()
            pdfMode = "vision"
        } else {
            stopPhoneConnection()
            pdfMode = "ocr"
        }
        selectedModelId = ""
        if (currentStep === 2) reloadPdfModels()
    }

    onPdfModeChanged: {
        selectedModelId = ""
        if (currentStep === 2) reloadPdfModels()
    }

    Component.onDestruction: stopPhoneConnection()

    // ── 步骤指示器 ──
    Frame {
        Layout.fillWidth: true; padding: 16
        RowLayout {
            anchors.left: parent.left; anchors.right: parent.right; spacing: 0
            Repeater {
                model: [{ label: qsTr("上传试卷"), step: 1 }, { label: qsTr("选择模型"), step: 2 }, { label: qsTr("结果导出"), step: 3 }]
                Item {
                    Layout.fillWidth: true; implicitHeight: childrenRect.height
                    Rectangle { id: dot; anchors.horizontalCenter: parent.horizontalCenter; implicitWidth: 28; implicitHeight: 28; radius: 14; color: stepColor(modelData.step)
                        Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 11; font.bold: true; text: modelData.step < currentStep ? "\u2713" : modelData.step } }
                    Text { anchors.top: dot.bottom; anchors.topMargin: 4; anchors.horizontalCenter: dot.horizontalCenter; text: modelData.label; typography: Typography.Caption; color: modelData.step === currentStep ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.textSecondaryColor }
                    Rectangle { visible: index < 2; anchors.left: dot.right; anchors.leftMargin: 4; anchors.right: parent.right; anchors.verticalCenter: dot.verticalCenter; implicitHeight: 2; radius: 1; color: modelData.step < currentStep ? Theme.currentTheme.colors.successColor : Theme.currentTheme.colors.controlBorderStrongColor }
                    Rectangle { visible: index > 0; anchors.right: dot.left; anchors.rightMargin: 4; anchors.left: parent.left; anchors.verticalCenter: dot.verticalCenter; implicitHeight: 2; radius: 1; color: modelData.step <= currentStep ? Theme.currentTheme.colors.successColor : Theme.currentTheme.colors.controlBorderStrongColor }
                }
            }
        }
    }

    // ── 步骤 1: 上传试卷 ──
    Frame {
        visible: currentStep === 1; Layout.fillWidth: true; padding: 20
        ColumnLayout { width: parent.width; spacing: 16
            Text { text: qsTr("上传试卷"); typography: Typography.BodyStrong }
            Text { text: qsTr("选择一种上传方式"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }

            RowLayout { spacing: 12
                RadioButton {
                    id: pdfRadio
                    text: qsTr("上传 PDF 文件")
                    checked: uploadMode === "pdf"
                    onCheckedChanged: if (checked) uploadMode = "pdf"
                }
                RadioButton {
                    id: phoneRadio
                    text: qsTr("连接手机 Lume")
                    checked: uploadMode === "phone"
                    onCheckedChanged: if (checked) uploadMode = "phone"
                }
            }

            // PDF upload area
            Frame {
                visible: uploadMode === "pdf"
                Layout.fillWidth: true
                implicitHeight: pdfFile !== "" ? 100 : 140
                hoverable: true
                TapHandler {
                    onTapped: {
                        var path = api.openFileDialog("PDF 文件 (*.pdf)")
                        if (path) {
                            pdfFile = path
                            pdfFileName = path.split("/").pop().split("\\").pop()
                        }
                    }
                }
                ColumnLayout { anchors.centerIn: parent; spacing: 8
                    Icon { icon: pdfFile !== "" ? "ic_fluent_document_pdf_20_regular" : "ic_fluent_arrow_upload_20_regular"; size: 32; Layout.alignment: Qt.AlignHCenter }
                    Text { text: pdfFileName !== "" ? pdfFileName : qsTr("点击选择 PDF 文件"); typography: Typography.Body; Layout.alignment: Qt.AlignHCenter }
                    Text { text: pdfFile !== "" ? qsTr("点击重新选择") : qsTr("未选择文件"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; Layout.alignment: Qt.AlignHCenter }
                }
            }

            // Phone connection area — single ColumnLayout, no overlapping children
            Frame {
                visible: uploadMode === "phone"
                Layout.fillWidth: true
                padding: 16

                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    // ── waiting-for-connection section ──
                    Text {
                        visible: !phoneConnected
                        text: qsTr("在同一局域网手机上输入IP连接")
                        typography: Typography.BodyStrong
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: !phoneConnected
                        text: phoneLanIp !== "" ? phoneLanIp : qsTr("获取中...")
                        font.pixelSize: 40
                        font.bold: true
                        color: Theme.currentTheme.colors.primaryColor
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: !phoneConnected
                        text: qsTr("网络：") + (phoneNetworkName !== "" ? phoneNetworkName : qsTr("未知网络"))
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.textSecondaryColor
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        visible: !phoneConnected
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 8
                        BusyIndicator { running: true; implicitWidth: 18; implicitHeight: 18 }
                        Text { text: qsTr("等待手机连接..."); color: Theme.currentTheme.colors.textSecondaryColor }
                    }

                    // ── connected section ──
                    RowLayout {
                        visible: phoneConnected
                        spacing: 8
                        Rectangle {
                            implicitWidth: 10; implicitHeight: 10; radius: 5
                            color: Theme.currentTheme.colors.systemSuccessColor
                        }
                        Text { text: qsTr("连接成功！"); typography: Typography.BodyStrong; color: Theme.currentTheme.colors.systemSuccessColor }
                        Item { Layout.fillWidth: true }
                        Text { text: phoneImageCount + qsTr(" 张已上传"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }

                    Text {
                        visible: phoneConnected
                        text: qsTr("手机端拍照后，下方会自动显示预览")
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.textSecondaryColor
                    }

                    // Image previews with hover controls
                    Frame {
                        visible: phoneConnected && phoneImageCount > 0
                        Layout.fillWidth: true
                        implicitHeight: Math.min(180, Math.ceil(phoneImageCount / 4) * 140 + 16)
                        Flickable {
                            anchors.fill: parent
                            contentWidth: phonePreviewRow.width
                            contentHeight: phonePreviewRow.height
                            clip: true
                            Row {
                                id: phonePreviewRow
                                spacing: 8
                                Repeater {
                                    model: phoneImageModel
                                    Frame {
                                        id: previewFrame
                                        width: 100; height: 130; padding: 4
                                        property int imgIndex: index

                                        Image {
                                            anchors.fill: parent
                                            source: model.filePath
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                        }

                                        MouseArea {
                                            id: hoverArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                        }

                                        // Hover overlay – shown when mouse is over
                                        ColumnLayout {
                                            visible: hoverArea.containsMouse
                                            anchors.top: parent.top
                                            anchors.right: parent.right
                                            anchors.margins: 2
                                            spacing: 2

                                            Rectangle {
                                                implicitWidth: 22; implicitHeight: 22; radius: 4
                                                color: "#B0000000"
                                                visible: imgIndex > 0
                                                Text { text: "\u25B2"; font.pixelSize: 12; color: "white"; anchors.centerIn: parent }
                                                TapHandler { onTapped: movePhoneImageLocally(imgIndex, imgIndex - 1) }
                                            }

                                            Rectangle {
                                                implicitWidth: 22; implicitHeight: 22; radius: 4
                                                color: "#B0000000"
                                                visible: imgIndex < phoneImageCount - 1
                                                Text { text: "\u25BC"; font.pixelSize: 12; color: "white"; anchors.centerIn: parent }
                                                TapHandler { onTapped: movePhoneImageLocally(imgIndex, imgIndex + 1) }
                                            }

                                            Rectangle {
                                                implicitWidth: 22; implicitHeight: 22; radius: 4
                                                color: "#B0CC0000"
                                                Text { text: "\u2715"; font.pixelSize: 12; color: "white"; anchors.centerIn: parent }
                                                TapHandler { onTapped: deletePhoneImageLocally(imgIndex) }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty placeholder when connected but no images yet
                    Frame {
                        visible: phoneConnected && phoneImageCount === 0
                        Layout.fillWidth: true
                        implicitHeight: 120
                        ColumnLayout {
                            anchors.centerIn: parent
                            Icon { icon: "ic_fluent_image_20_regular"; size: 32; Layout.alignment: Qt.AlignHCenter; color: Theme.currentTheme.colors.textSecondaryColor }
                            Text { text: qsTr("暂无图片，请在手机端拍照上传"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; Layout.alignment: Qt.AlignHCenter }
                        }
                    }
                }
            }

            Button {
                text: qsTr("下一步：选择模型")
                highlighted: true
                enabled: {
                    if (uploadMode === "pdf") return pdfFile !== ""
                    if (uploadMode === "phone") return phoneImageCount > 0
                    return false
                }
                onClicked: {
                    if (uploadMode === "phone") api.proceedOnPhone()
                    reloadPdfModels()
                    currentStep = 2
                }
            }
        }
    }

    // ── 步骤 2: 选择模式 + 模型 ──
    Frame {
        visible: currentStep === 2; Layout.fillWidth: true; padding: 20
        ColumnLayout { width: parent.width; spacing: 12
            Text { text: qsTr("选择 AI 模型与模式"); typography: Typography.BodyStrong }

            Frame {
                visible: uploadMode === "phone"
                Layout.fillWidth: true
                padding: 12
                RowLayout { spacing: 8
                    Icon { icon: "ic_fluent_lightbulb_20_regular"; size: 20; color: Theme.currentTheme.colors.primaryColor }
                    Text { text: qsTr("通过手机上传的方式选择视觉模型效果更好"); color: Theme.currentTheme.colors.primaryColor; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }

            RowLayout { spacing: 12
                RadioButton {
                    text: qsTr("视觉模型模式 — 直接识别试卷图片")
                    checked: pdfMode === "vision"
                    onCheckedChanged: if (checked) pdfMode = "vision"
                }
                RadioButton {
                    visible: uploadMode === "pdf"
                    text: qsTr("OCR 模式 — 先 OCR 识别文字再整理")
                    checked: pdfMode === "ocr"
                    onCheckedChanged: if (checked) pdfMode = "ocr"
                }
            }
            CheckBox { visible: pdfMode === "vision"; text: qsTr("分批发送（每批最多 9 张图片）"); checked: batchMode; onCheckedChanged: batchMode = checked }
            CheckBox { visible: pdfMode === "ocr"; text: qsTr("分两次进行（防止模型上下文不足）"); checked: splitMode; onCheckedChanged: splitMode = checked }

            ComboBox {
                id: modelCombo
                Layout.fillWidth: true
                property var data: []
                model: pdfModelList
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

            RowLayout { spacing: 12
                Button { text: qsTr("上一步"); onClicked: currentStep = 1 }
                Button {
                    text: qsTr("确认，开始 AI 整理"); highlighted: true; enabled: selectedModelId !== ""
                    onClicked: {
                        currentStep = 3; isGenerating = true; fullContent = ""; thinkingContent = ""
                        _contentBuffer = ""; _thinkingBuffer = ""; flushTimer.stop()
                        resultStatus = qsTr("正在处理...")
                        api.notifyPhoneProcessingStarted()
                        if (uploadMode === "phone") {
                            var imagesJson = api.getPhoneImagesJson()
                            api.startVisionGeneration(imagesJson, selectedModelId, selectedModelThinking, batchMode)
                        } else if (pdfMode === "ocr") {
                            api.startPdfOcr(pdfFile)
                        } else {
                            api.startPdfToImages(pdfFile)
                        }
                    }
                }
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
                        var r = JSON.parse(api.savePdfDocx(fullContent))
                        if (r.ok) floatLayer.createInfoBar({ severity: Severity.Success, title: qsTr("成功"), text: qsTr("Word 文档已保存"), timeout: 3000 })
                        else if (!r.cancelled) floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("导出失败"), text: r.error || "", timeout: 5000 })
                    }
                }
                Button { text: qsTr("导出 PPT"); highlighted: true
                    onClicked: {
                        var r = JSON.parse(api.savePdfPptx(fullContent))
                        if (r.ok) floatLayer.createInfoBar({ severity: Severity.Success, title: qsTr("成功"), text: qsTr("PPT 文档已保存"), timeout: 3000 })
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
        function onOcrProgress(pct, status) { ocrProgress = pct; resultStatus = status }
        function onOcrDone(pages) { ocrProgress = 100; resultStatus = qsTr("OCR 完成，正在调用 AI..."); api.startPdfGeneration(JSON.stringify(pages), selectedModelId, selectedModelThinking, splitMode) }
        function onOcrError(err) { isGenerating = false; resultStatus = qsTr("OCR 失败"); floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("错误"), text: err, timeout: 5000 }) }
        function onPdfToImagesDone(images) { resultStatus = qsTr("图片转换完成，正在调用 AI..."); api.startVisionGeneration(JSON.stringify(images), selectedModelId, selectedModelThinking, batchMode) }
        function onPdfToImagesError(err) { isGenerating = false; resultStatus = qsTr("转换失败"); floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("错误"), text: err, timeout: 5000 }) }
        function onPdfChunk(chunk) {
            try {
                var obj = JSON.parse(chunk)
                if (obj.reasoning) { _thinkingBuffer += obj.reasoning; resultStatus = qsTr("AI 正在思考...") }
                if (obj.content) { _contentBuffer += obj.content; resultStatus = qsTr("AI 正在生成...") }
                if (!flushTimer.running) flushTimer.restart()
            } catch(e) {}
        }
        function onPdfDone(content) {
            flushTimer.stop()
            if (_contentBuffer) { fullContent += _contentBuffer; _contentBuffer = "" }
            if (_thinkingBuffer) { thinkingContent += _thinkingBuffer; _thinkingBuffer = "" }
            fullContent = content; isGenerating = false; resultStatus = qsTr("生成完成"); api.notifyPhoneProcessingComplete()
        }
        function onPdfError(err) {
            flushTimer.stop()
            if (_contentBuffer) { fullContent += _contentBuffer; _contentBuffer = "" }
            if (_thinkingBuffer) { thinkingContent += _thinkingBuffer; _thinkingBuffer = "" }
            isGenerating = false; resultStatus = qsTr("生成出错")
            floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("错误"), text: err, timeout: 5000 })
        }

        function onPhoneConnected() { phoneConnected = true }
        function onPhoneDisconnected() { phoneConnected = false }
        function onPhoneImageReceived(filePath) { phoneImageModel.append({ filePath: filePath }); phoneImageCount = phoneImageModel.count }
        function onPhoneImagesChanged() {
            // Backend order changed (phone or desktop initiated) — rebuild.
            phoneImageModel.clear()
            try {
                var paths = JSON.parse(api.getPhoneImagePathsJson())
                for (var i = 0; i < paths.length; i++) {
                    phoneImageModel.append({ filePath: paths[i] })
                }
                phoneImageCount = phoneImageModel.count
            } catch (e) {}
        }
        function onPhoneStartRequested() {
            // Phone clicked "下一步" — mirror the desktop flow.
            if (currentStep === 1 && uploadMode === "phone") {
                api.proceedOnPhone()
                reloadPdfModels()
                currentStep = 2
            }
        }
    }
}
