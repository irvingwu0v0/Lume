import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI
import "../components"

FluentPage {
    layer.enabled: false
    id: root
    title: ""
    horizontalPadding: 56

    // ── Hero 区域 ──
    ColumnLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: 8
        Item { implicitHeight: 32 }

        Text {
            text: "Lume."
            font.pixelSize: 48
            font.bold: true
            font.family: "Georgia"
            color: Theme.currentTheme.colors.primaryColor
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: qsTr("Light Up My English")
            typography: Typography.Subtitle
            color: Theme.currentTheme.colors.textSecondaryColor
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: qsTr("AI 驱动的英语教学材料生成工具")
            typography: Typography.Body
            color: Theme.currentTheme.colors.textTertialyColor
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
        }
    }

    // ── 功能卡片 ──
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: 24
        Layout.topMargin: 32

        FeatureCard {
            iconName: "ic_fluent_document_20_regular"
            title: qsTr("试卷转换")
            description: qsTr("上传 PDF 试卷或连接手机拍照，AI 智能识别并整理为标准化文档，支持导出 Word 与 PPT")
            onClicked: window.navigationView.push(Qt.resolvedUrl("PdfConvertPage.qml"))
        }
        FeatureCard {
            iconName: "ic_fluent_headphones_20_regular"
            title: qsTr("听力材料生成")
            description: qsTr("上传音频文件，自动转写文字，AI 整理为听力练习材料，一键导出")
            onClicked: window.navigationView.push(Qt.resolvedUrl("ListeningPage.qml"))
        }
        FeatureCard {
            iconName: "ic_fluent_pen_20_regular"
            title: qsTr("作文思路生成")
            description: qsTr("输入阅读理解原文，AI 生成写作思路、情节结构与高分表达")
            onClicked: window.navigationView.push(Qt.resolvedUrl("WritingPage.qml"))
        }
    }

    Item { Layout.fillHeight: true }
}
