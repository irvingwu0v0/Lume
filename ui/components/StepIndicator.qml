import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

// Three-or-more step progress header used by every workflow page.
Frame {
    id: root
    Layout.fillWidth: true
    padding: 16

    property int currentStep: 1
    property var labels: []

    function stepColor(step) {
        if (step < root.currentStep) return Theme.currentTheme.colors.successColor
        if (step === root.currentStep) return Theme.currentTheme.colors.primaryColor
        return Theme.currentTheme.colors.controlBorderStrongColor
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        Repeater {
            model: root.labels

            Item {
                Layout.fillWidth: true
                implicitHeight: childrenRect.height

                Rectangle {
                    id: dot
                    anchors.horizontalCenter: parent.horizontalCenter
                    implicitWidth: 28; implicitHeight: 28; radius: 14
                    color: root.stepColor(index + 1)
                    Text {
                        anchors.centerIn: parent
                        color: "white"; font.pixelSize: 11; font.bold: true
                        text: (index + 1) < root.currentStep ? "\u2713" : (index + 1)
                    }
                }

                Text {
                    anchors.top: dot.bottom; anchors.topMargin: 4
                    anchors.horizontalCenter: dot.horizontalCenter
                    text: modelData
                    typography: Typography.Caption
                    color: (index + 1) === root.currentStep
                        ? Theme.currentTheme.colors.primaryColor
                        : Theme.currentTheme.colors.textSecondaryColor
                }

                Rectangle {
                    visible: index < root.labels.length - 1
                    anchors.left: dot.right; anchors.leftMargin: 4
                    anchors.right: parent.right
                    anchors.verticalCenter: dot.verticalCenter
                    implicitHeight: 2; radius: 1
                    color: (index + 1) < root.currentStep
                        ? Theme.currentTheme.colors.successColor
                        : Theme.currentTheme.colors.controlBorderStrongColor
                }

                Rectangle {
                    visible: index > 0
                    anchors.right: dot.left; anchors.rightMargin: 4
                    anchors.left: parent.left
                    anchors.verticalCenter: dot.verticalCenter
                    implicitHeight: 2; radius: 1
                    color: (index + 1) <= root.currentStep
                        ? Theme.currentTheme.colors.successColor
                        : Theme.currentTheme.colors.controlBorderStrongColor
                }
            }
        }
    }
}
