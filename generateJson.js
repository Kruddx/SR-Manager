function generateJson() {
    const instances = document.getElementById('instances').value;
    if (!instances) {
        alert('Выберите instances');
        return;
    }

    // Показываем загрузку
    document.getElementById('result').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    document.getElementById('stats').style.display = 'block';
    document.getElementById('playerCount').textContent = 'загрузка...';
    document.getElementById('instancesName').textContent = instances;

    fetch(`/generate/${encodeURIComponent(instances)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('outputData').value = data.encoded_data;
                document.getElementById('result').style.display = 'block';
                document.getElementById('error').style.display = 'none';
                document.getElementById('playerCount').textContent = data.total_players;
                document.getElementById('instancesName').textContent = data.instances;
            } else {
                showError(data.error);
                document.getElementById('stats').style.display = 'none';
            }
        })
        .catch(error => {
            showError('Ошибка при генерации JSON: ' + error);
            document.getElementById('stats').style.display = 'none';
        });
}