import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import RinUI

// Model picker that reads the shared model list from the backend.
// `filterVision` hides non-vision models (used by the vision pipelines).
ComboBox {
    id: root
    Layout.fillWidth: true
    placeholderText: qsTr("请选择模型...")

    property bool filterVision: false

    readonly property int modelCount: _models.length
    readonly property string selectedModelId:
        (currentIndex >= 0 && currentIndex < _models.length) ? _models[currentIndex].id : ""
    readonly property bool selectedModelThinking:
        (currentIndex >= 0 && currentIndex < _models.length) ? _models[currentIndex].thinking_enabled : false

    property var _models: []

    model: ListModel { id: modelList }

    function reload() {
        modelList.clear()
        var models = []
        try {
            var all = JSON.parse(api.getModelsJson())
            for (var i = 0; i < all.length; i++) {
                if (root.filterVision && !all[i].vision_enabled)
                    continue
                var label = all[i].alias
                if (all[i].thinking_enabled) label += " [思考]"
                if (all[i].vision_enabled) label += " [视觉]"
                models.push(all[i])
                modelList.append({ text: label })
            }
        } catch (e) {}
        _models = models
        currentIndex = -1
        currentIndex = 0
    }
}
