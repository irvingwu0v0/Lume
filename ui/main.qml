import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

FluentWindow {
    id: window
    visible: true
    width: 1280
    height: 820
    minimumWidth: 960
    minimumHeight: 640
    title: "Lume — Light Up My English"

    navigationView.navExpandWidth: 280

    navigationItems: [
        {
            title: qsTr("首页"),
            page: Qt.resolvedUrl("pages/HomePage.qml"),
            icon: "ic_fluent_home_20_regular",
            position: Position.Top
        },
        {
            title: qsTr("试卷转换"),
            page: Qt.resolvedUrl("pages/PdfConvertPage.qml"),
            icon: "ic_fluent_document_20_regular"
        },
        {
            title: qsTr("听力材料生成"),
            page: Qt.resolvedUrl("pages/ListeningPage.qml"),
            icon: "ic_fluent_headphones_20_regular"
        },
        {
            title: qsTr("作文思路生成"),
            page: Qt.resolvedUrl("pages/WritingPage.qml"),
            icon: "ic_fluent_pen_20_regular"
        },
        {
            title: qsTr("设置"),
            page: Qt.resolvedUrl("pages/SettingsPage.qml"),
            icon: "ic_fluent_settings_20_regular",
            position: Position.Bottom
        }
    ]

    Component.onCompleted: {
        Theme.setThemeColor("#539dda")
    }

    Connections {
        target: api
        function onToastMessage(msg, type) {
            floatLayer.createInfoBar({
                severity: type === "success" ? Severity.Success : Severity.Error,
                title: type === "success" ? qsTr("成功") : qsTr("错误"),
                text: msg,
                timeout: 3000
            })
        }
    }
}
