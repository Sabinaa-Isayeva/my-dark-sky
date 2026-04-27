from flask import Flask, jsonify, render_template, request

from weather_service import WeatherService, WeatherServiceError


def create_app():
    app = Flask(__name__)
    weather_service = WeatherService()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/search")
    def search_locations():
        query = request.args.get("q", "").strip()
        if len(query) < 2:
            return jsonify({"results": []})

        try:
            results = weather_service.search_locations(query)
        except WeatherServiceError as exc:
            return jsonify({"error": str(exc)}), 502

        return jsonify({"results": results})

    @app.get("/api/weather")
    def weather_by_coordinates():
        latitude = request.args.get("lat", type=float)
        longitude = request.args.get("lon", type=float)
        selected_date = request.args.get("date", "").strip()
        label = request.args.get("label", "").strip() or "Selected Location"

        if latitude is None or longitude is None or not selected_date:
            return jsonify({"error": "lat, lon, and date are required."}), 400

        try:
            payload = weather_service.get_weather_for_date(
                latitude=latitude,
                longitude=longitude,
                selected_date=selected_date,
                label=label,
            )
        except WeatherServiceError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(payload)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found"}), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
