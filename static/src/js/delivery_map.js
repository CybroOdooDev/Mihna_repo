/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

class DeliveryMap extends Component {
    /**
     * Component setup lifecycle
     */
    setup() {

        onMounted(async () => {
            await this.loadMap();
        });
    }
    /**
     * Load and render map
     */
    async loadMap() {
        /*
        ---------------------------------------------------------
        Get current record data
        ---------------------------------------------------------
        */
        const record = this.props.record.data;
        const source = record.source_location;
        const destination = record.destination_location;
        /*
        ---------------------------------------------------------
        Stop if fields are empty
        ---------------------------------------------------------
        */
        if (!source || !destination) {
            return;
        }
        /*
        ---------------------------------------------------------
        Fetch source coordinates
        ---------------------------------------------------------
        */
        const sourceData = await rpc(
            '/delivery_map/get_coordinates',
            {
                location: source,
            }
        );
        /*
        ---------------------------------------------------------
        Fetch destination coordinates
        ---------------------------------------------------------
        */
        const destinationData = await rpc(
            '/delivery_map/get_coordinates',
            {
                location: destination,
            }
        );
        /*
        ---------------------------------------------------------
        Stop if coordinates not found
        ---------------------------------------------------------
        */
        if (!sourceData || !destinationData) {
            return;
        }
        /*
        ---------------------------------------------------------
        Create map
        ---------------------------------------------------------
        */
        const map = L.map('delivery_map').setView(
            [
                sourceData.lat,
                sourceData.lon
            ],
            6
        );
        /*
        ---------------------------------------------------------
        Load OpenStreetMap tiles
        ---------------------------------------------------------
        */
        L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                attribution:
                    '&copy; OpenStreetMap contributors'
            }
        ).addTo(map);
         /*
        ---------------------------------------------------------
        Add source marker
        ---------------------------------------------------------
        */
        L.marker([
            sourceData.lat,
            sourceData.lon
        ])
        .addTo(map)
        .bindPopup('Source');
        /*
        ---------------------------------------------------------
        Add destination marker
        ---------------------------------------------------------
        */
        L.marker([
            destinationData.lat,
            destinationData.lon
        ])
        .addTo(map)
        .bindPopup('Destination');

        L.polyline(
            [
                [
                    sourceData.lat,
                    sourceData.lon
                ],
                [
                    destinationData.lat,
                    destinationData.lon
                ]
            ],
            {
                color: 'blue'
            }
        ).addTo(map);
    }
}
/*
---------------------------------------------------------
QWeb Template Mapping
---------------------------------------------------------
*/
DeliveryMap.template = 'delivery_map.DeliveryMap';
/*
---------------------------------------------------------
Register Widget
---------------------------------------------------------
*/
registry.category("view_widgets").add("delivery_map_widget", {component: DeliveryMap,});