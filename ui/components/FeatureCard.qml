import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

Frame {
    id: root
    property string iconName: ""
    property string title: ""
    property string description: ""
    signal clicked()

    implicitWidth: 280
    implicitHeight: 200
    radius: 8
    hoverable: true

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 12

        Icon {
            icon: root.iconName
            size: 32
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: root.title
            typography: Typography.BodyStrong
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: root.description
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.maximumWidth: 240
            Layout.alignment: Qt.AlignHCenter
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        z: 1
        onClicked: root.clicked()
    }
}
