document.addEventListener('DOMContentLoaded', function () {

    const slug = window.location.pathname.split('/').filter(p => p).pop();

    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/rooms/${slug}/`);

    socket.onopen = function (event) {
        console.log('Websocket подключён!');
    };

    socket.onerror = function (error) {
        console.log('Ошибка:', error);
    };

    socket.onclose = function (event) {
        console.log('Соединение закрыто');
    };

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.action === 'voted' || data.action === 'unvoted') {
            let room_track_id = data['room_track_id'];
            let new_votes_count = data['new_votes_count'];
            let new_order = data['new_order'];
            let vote_counter = document.querySelector(`#votes-${room_track_id}`);
            if (vote_counter) {
                vote_counter.innerText = `${new_votes_count}`;
            }
            let tracks = document.querySelector(`.tracks-container`);
            new_order.forEach(id => {
                let child = document.querySelector(`div.track-container[data-track-id="${id}"]`);
                tracks.appendChild(child);
            });
        } else if (data.action === 'delete_track') {
            const trackId = data.track_id;
            const trackElement = document.querySelector(`.track-container[data-track-id="${trackId}"]`);
            if (trackElement) {
                trackElement.remove();
                const trackCounter = document.querySelector('.tracks-counter');
                if (trackCounter) {
                    let text = trackCounter.innerText;
                    let match = text.match(/\d+/);
                    if (match) {
                        let currentCount = parseInt(match[0]);
                        trackCounter.innerText = text.replace(currentCount, currentCount - 1);
                    }
                }
            }
        }
    };

    const buttons = document.querySelectorAll('button[data-track-id]');

    for (const button of buttons) {
        button.addEventListener('click', () => {
            const trackId = button.dataset.trackId
            socket.send(JSON.stringify({action: 'vote', room_track_id: trackId}));
        });
    }

    const delete_track_buttons = document.querySelectorAll('.delete-track-btn');
    for (const button of delete_track_buttons) {
        button.addEventListener('click', () => {
            let trackId = button.dataset.trackId;
            let roomSlug = slug;
            let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            if (!confirm('Удалить трек?')) return;

            fetch(`/rooms/${roomSlug}/delete_track/${trackId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
            })
                .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP server error! Status ${response.status}`);
                        }
                        return response.json();
                    }
                )
                .then(data => {
                    if (data.success) {
                        const track = document.querySelector(`div.track-container[data-track-id="${trackId}"]`);
                        if (track) {
                            track.remove();
                        }
                        const trackCounter = document.querySelector(`.tracks-counter`);
                        if (trackCounter) {
                            let text = trackCounter.innerText;
                            let match = text.match(/\d+/);
                            if (match) {
                                let currentCount = parseInt(match[0]);
                                trackCounter.innerText = text.replace(currentCount, currentCount - 1);

                            }
                        }
                    } else alert(data.error);
                })
                .catch(error => {
                    console.error('Ошибка: ', error);
                    alert('Не удалось удалить трек');
                });
        });
    }
});
