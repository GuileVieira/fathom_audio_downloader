function download(filename, text) {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:application/json;charset=utf-8,' + encodeURIComponent(text));
    element.setAttribute('download', filename);
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  }
  
  // Exporta localStorage
  download('local_storage.json', JSON.stringify(localStorage));
  
  // Exporta sessionStorage
  download('session_storage.json', JSON.stringify(sessionStorage));
  
  // Exporta cookies
  /*
  (function() {
    const cookies = document.cookie.split('; ').map(cookieStr => {
      const [name, ...rest] = cookieStr.split('=');
      return { name, value: rest.join('=') };
    });
    download('cookies.json', JSON.stringify(cookies, null, 2));
  })();*/