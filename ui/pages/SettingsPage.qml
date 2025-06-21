import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

FluentPage {
    layer.enabled: false
    id: root
    title: qsTr("设置")
    horizontalPadding: 56

    property string editingModelId: ""

    // ── OCR 配置 ──
    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Umi OCR API")
        description: qsTr("用于 PDF 试卷的 OCR 文字识别服务")
        icon.name: "ic_fluent_scan_20_regular"

        TextField {
            id: ocrHostField
            text: "127.0.0.1"
            width: 140
            placeholderText: "127.0.0.1"
        }
        TextField {
            id: ocrPortField
            text: "1224"
            width: 80
            placeholderText: "1224"
        }
        Button {
            text: qsTr("保存")
            highlighted: true
            onClicked: api.saveOcrConfig(ocrHostField.text, ocrPortField.text)
        }
        Button {
            text: qsTr("测试")
            onClicked: {
                var url = "http://" + ocrHostField.text + ":" + ocrPortField.text + "/"
                var r = JSON.parse(api.testOcrConnection(url))
                if (r.ok)
                    floatLayer.createInfoBar({
                        severity: Severity.Success,
                        title: qsTr("OCR 连接成功"),
                        text: qsTr("Umi OCR 服务正常"),
                        timeout: 3000
                    })
                else
                    floatLayer.createInfoBar({
                        severity: Severity.Error,
                        title: qsTr("OCR 连接失败"),
                        text: r.detail || qsTr("无法连接到 OCR 服务"),
                        timeout: 5000
                    })
            }
        }
    }

    // ── 分隔线 ──
    Rectangle {
        Layout.fillWidth: true
        height: 1
        color: "#E0E0E0"
        Layout.topMargin: 8
        Layout.bottomMargin: 8
    }

    // ── AI 模型管理 ──
    SettingCard {
        Layout.fillWidth: true
        title: qsTr("AI 模型列表")
        description: qsTr("管理用于生成的 AI 模型配置")
        icon.name: "ic_fluent_bot_20_regular"

        Button {
            text: qsTr("添加模型")
            highlighted: true
            onClicked: {
                root.editingModelId = ""
                aliasFld.text = ""
                urlFld.text = ""
                nameFld.text = ""
                keyFld.text = ""
                thinkChk.checked = false
                visionChk.checked = false
                modelDialog.open()
            }
        }
    }

    // ── 模型卡片列表 ──
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8

        Repeater {
            model: ListModel { id: settingsModelList }

            delegate: Frame {
                Layout.fillWidth: true
                padding: 14

                RowLayout {
                    anchors.fill: parent
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 2

                        RowLayout {
                            spacing: 6
                            Text {
                                text: model.alias
                                typography: Typography.BodyStrong
                            }
                            Rectangle { visible: model.thinking_enabled; implicitWidth: 30; implicitHeight: 16; radius: 3; color: Theme.currentTheme.colors.primaryColor; Text { anchors.centerIn: parent; text: qsTr("思考"); font.pixelSize: 9; color: "white" } }
                            Rectangle { visible: model.vision_enabled; implicitWidth: 30; implicitHeight: 16; radius: 3; color: Theme.currentTheme.colors.primaryColor; Text { anchors.centerIn: parent; text: qsTr("视觉"); font.pixelSize: 9; color: "white" } }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: model.model_name + "  ·  " + model.base_url
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            elide: Text.ElideRight
                        }
                    }

                    RowLayout {
                        spacing: 8
                        Button { text: qsTr("编辑"); flat: true; onClicked: { root.editingModelId = model.id; aliasFld.text = model.alias; urlFld.text = model.base_url; nameFld.text = model.model_name; keyFld.text = model.api_key || ""; thinkChk.checked = model.thinking_enabled; visionChk.checked = model.vision_enabled; modelDialog.open() } }
                        Button { text: qsTr("测试"); flat: true; onClicked: { var r = JSON.parse(api.testModel(model.id)); if (r.ok) floatLayer.createInfoBar({ severity: Severity.Success, title: qsTr("连接成功"), text: qsTr("延迟 ") + r.elapsed_ms + "ms", timeout: 3000 }); else floatLayer.createInfoBar({ severity: Severity.Error, title: qsTr("连接失败"), text: r.detail || r.status || qsTr("未知错误"), timeout: 5000 }) } }
                        Button { text: qsTr("删除"); flat: true; onClicked: { delTargetId = model.id; delDialog.open() } }
                    }
                }
            }
        }
    }

    Text {
        visible: settingsModelList.count === 0
        text: qsTr("尚未添加任何模型，点击上方「添加模型」开始")
        typography: Typography.Body
        color: Theme.currentTheme.colors.textSecondaryColor
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 24
    }

    // ── 添加 / 编辑模型对话框 ──
    Dialog {
        id: modelDialog
        title: root.editingModelId ? qsTr("编辑 AI 模型") : qsTr("添加 AI 模型")

        TextField {
            id: aliasFld
            Layout.fillWidth: true
            placeholderText: qsTr("模型代称（如：DeepSeek V4 Pro）")
        }
        TextField {
            id: urlFld
            Layout.fillWidth: true
            placeholderText: qsTr("Base URL（如：https://api.deepseek.com）")
        }
        TextField {
            id: nameFld
            Layout.fillWidth: true
            placeholderText: qsTr("模型名称（如：deepseek-v4-pro）")
        }
        TextField {
            id: keyFld
            Layout.fillWidth: true
            placeholderText: qsTr("API Key")
            echoMode: TextInput.Password
        }
        CheckBox {
            id: thinkChk
            text: qsTr("开启思考模式（推理模型）")
            Layout.fillWidth: true
        }
        CheckBox {
            id: visionChk
            text: qsTr("视觉模型（Vision）")
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("取消")
                onClicked: modelDialog.reject()
            }
            Button {
                text: qsTr("保存")
                highlighted: true
                onClicked: {
                    if (!aliasFld.text || !urlFld.text || !nameFld.text || !keyFld.text) {
                        floatLayer.createInfoBar({
                            severity: Severity.Warning,
                            title: qsTr("提示"),
                            text: qsTr("请填写所有字段"),
                            timeout: 3000
                        })
                        return
                    }
                    if (root.editingModelId)
                        api.updateModel(root.editingModelId, aliasFld.text, urlFld.text, nameFld.text, keyFld.text, thinkChk.checked, visionChk.checked)
                    else
                        api.addModel(aliasFld.text, urlFld.text, nameFld.text, keyFld.text, thinkChk.checked, visionChk.checked)
                    modelDialog.accept()
                }
            }
        }
    }

    // ── 删除确认对话框 ──
    property string delTargetId: ""

    Dialog {
        id: delDialog
        title: qsTr("确认删除")

        Text {
            Layout.fillWidth: true
            text: qsTr("确定要删除此模型吗？此操作不可撤销。")
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("取消")
                onClicked: delDialog.reject()
            }
            Button {
                text: qsTr("确认删除")
                highlighted: true
                onClicked: {
                    api.deleteModel(root.delTargetId)
                    delDialog.accept()
                }
            }
        }
    }

    // ── 数据加载 ──
    Component.onCompleted: loadModels()

    function loadModels() {
        settingsModelList.clear()
        try {
            var m = JSON.parse(api.getModelsJson())
            for (var i = 0; i < m.length; i++)
                settingsModelList.append(m[i])
        } catch (e) {}
    }

    Connections {
        target: api
        function onModelsChanged() { root.loadModels() }
    }
}
