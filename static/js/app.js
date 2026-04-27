const locationSearch = document.getElementById("location-search");
const weatherDate = document.getElementById("weather-date");
const searchResults = document.getElementById("search-results");
const statusCard = document.getElementById("status-card");
const weatherPanel = document.getElementById("weather-panel");

const state = {
    selectedLocation: null,
};

function todayString() {
    return new Date().toISOString().split("T")[0];
}

function showStatus(message, type = "success") {
    statusCard.textContent = message;
    statusCard.className = `status-card mt-4 is-${type}`;
    statusCard.classList.remove("d-none");
}

function hideStatus() {
    statusCard.classList.add("d-none");
}

function setDefaultDate() {
    weatherDate.value = todayString();
}

function formatDateLabel(dateString) {
    return new Date(`${dateString}T12:00:00`).toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
    });
}

function metricCard(label, value) {
    return `
        <div class="metric-card">
            <span class="metric-label">${label}</span>
            <span class="metric-value">${value}</span>
        </div>
    `;
}

function hourCard(point) {
    const time = new Date(point.time).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });
    const precip = point.precipitation_probability ?? "N/A";
    return `
        <div class="hour-card">
            <span class="hour-time">${time}</span>
            <span class="hour-temp">${Math.round(point.temperature)}°</span>
            <span class="hour-summary">${point.weather_label}</span>
            <span class="metric-label mt-2">Wind ${Math.round(point.wind_speed)} km/h</span>
            <span class="metric-label">Rain chance ${precip === "N/A" ? precip : `${precip}%`}</span>
        </div>
    `;
}

function renderSearchResults(results) {
    if (!results.length) {
        searchResults.innerHTML = "";
        showStatus("No matching locations found. Try another city name.", "error");
        return;
    }

    hideStatus();
    searchResults.innerHTML = results
        .map(
            (result, index) => `
                <button class="search-result-btn" type="button" data-index="${index}">
                    ${result.label}
                    <small>${result.latitude.toFixed(2)}, ${result.longitude.toFixed(2)} • ${result.timezone || "Local timezone"}</small>
                </button>
            `
        )
        .join("");

    document.querySelectorAll(".search-result-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const index = Number(button.dataset.index);
            state.selectedLocation = results[index];
            locationSearch.value = results[index].label;
            searchResults.innerHTML = "";
            showStatus(`Selected ${results[index].label}`, "success");
        });
    });
}

async function searchLocation() {
    const query = locationSearch.value.trim();
    if (query.length < 2) {
        showStatus("Enter at least 2 characters to search for a location.", "error");
        return;
    }

    showStatus("Searching locations...");
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();

    if (!response.ok) {
        showStatus(data.error || "Search failed.", "error");
        return;
    }

    renderSearchResults(data.results);
}

function renderWeather(data) {
    const currentGrid = document.getElementById("current-weather-grid");
    const dailyGrid = document.getElementById("daily-summary-grid");
    const hourlyForecast = document.getElementById("hourly-forecast");

    document.getElementById("location-label").textContent = data.location.label;
    document.getElementById("date-label").textContent = formatDateLabel(data.selected_date);
    document.getElementById("headline-temp").textContent = Math.round(
        data.current_weather?.temperature ?? data.summary.temperature_max
    );
    document.getElementById("headline-summary").textContent =
        data.timeline === "past"
            ? `Historical conditions with ${data.summary.weather_label.toLowerCase()}.`
            : data.timeline === "future"
              ? `Forecast outlook with ${data.summary.weather_label.toLowerCase()}.`
              : `Live conditions right now with ${data.current_weather.weather_label.toLowerCase()}.`;

    const currentCards = [];
    if (data.current_weather) {
        currentCards.push(metricCard("Current Temp", `${Math.round(data.current_weather.temperature)} °C`));
        currentCards.push(metricCard("Feels Like", `${Math.round(data.current_weather.apparent_temperature)} °C`));
        currentCards.push(metricCard("Humidity", `${data.current_weather.humidity}%`));
        currentCards.push(metricCard("Wind", `${Math.round(data.current_weather.wind_speed)} km/h`));
    } else {
        currentCards.push(metricCard("Timeline", data.timeline === "past" ? "Historical day" : "Future forecast"));
        currentCards.push(metricCard("Weather", data.summary.weather_label));
    }
    currentGrid.innerHTML = currentCards.join("");

    dailyGrid.innerHTML = [
        metricCard("High / Low", `${Math.round(data.summary.temperature_max)}° / ${Math.round(data.summary.temperature_min)}°`),
        metricCard("Feels Like", `${Math.round(data.summary.apparent_max)}° / ${Math.round(data.summary.apparent_min)}°`),
        metricCard("Precipitation", `${data.summary.precipitation_sum ?? 0} mm`),
        metricCard(
            "Rain Chance",
            data.summary.precipitation_probability_max == null ? "Archive data" : `${data.summary.precipitation_probability_max}%`
        ),
        metricCard("Sunrise", data.summary.sunrise.split("T")[1]),
        metricCard("Sunset", data.summary.sunset.split("T")[1]),
        metricCard("Max Wind", `${Math.round(data.summary.wind_speed_max)} km/h`),
        metricCard("Coordinates", `${data.location.latitude.toFixed(2)}, ${data.location.longitude.toFixed(2)}`),
    ].join("");

    hourlyForecast.innerHTML = data.hourly.slice(0, 24).map(hourCard).join("");
    weatherPanel.classList.remove("d-none");
    showStatus("Weather updated successfully.");
}

async function requestWeather(latitude, longitude, label) {
    const selectedDate = weatherDate.value;
    if (!selectedDate) {
        showStatus("Choose a date first.", "error");
        return;
    }

    showStatus("Loading weather details...");
    const params = new URLSearchParams({
        lat: latitude,
        lon: longitude,
        date: selectedDate,
        label,
    });

    const response = await fetch(`/api/weather?${params.toString()}`);
    const data = await response.json();

    if (!response.ok) {
        showStatus(data.error || "Weather request failed.", "error");
        return;
    }

    renderWeather(data);
}

async function useCurrentLocation() {
    if (!navigator.geolocation) {
        showStatus("Your browser does not support geolocation.", "error");
        return;
    }

    showStatus("Requesting your current location...");
    navigator.geolocation.getCurrentPosition(
        async (position) => {
            state.selectedLocation = {
                label: "Current Location",
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
            };
            await requestWeather(
                position.coords.latitude,
                position.coords.longitude,
                "Current Location"
            );
        },
        () => {
            showStatus("Location access was denied. Search for a city instead.", "error");
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
        }
    );
}

document.getElementById("search-button").addEventListener("click", searchLocation);
document.getElementById("use-location-button").addEventListener("click", useCurrentLocation);
document.getElementById("today-button").addEventListener("click", () => {
    weatherDate.value = todayString();
    showStatus("Date reset to today.");
});

document.getElementById("weather-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!state.selectedLocation) {
        showStatus("Pick a searched city or use your current location first.", "error");
        return;
    }

    await requestWeather(
        state.selectedLocation.latitude,
        state.selectedLocation.longitude,
        state.selectedLocation.label
    );
});

locationSearch.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        await searchLocation();
    }
});

setDefaultDate();
hideStatus();
